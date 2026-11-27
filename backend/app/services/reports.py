"""PDF reports of a result (Phase 7, P7.01 and P7.04).

A report is asked for in a request, which stores the snapshot of what the app shows for
the result (app/reports/snapshot.py) and queues the drawing; the PDF is drawn in a task
(app/jobs/tasks/reports.py) and kept in file storage. Who may see the result may list and
download its reports; making one needs ``reports.request``.

Asking twice gives one report: while a report of the result is still being drawn, or when
the newest ready one already shows exactly the same, that report is returned instead of a
new version. An organisation may ask for at most ``DAILY_LIMIT`` reports a rolling day.
"""

import hashlib
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import Select, func, select, text, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.core.storage import get_storage
from app.models import Report, User
from app.models.enums import AdviceSubject, ReportStatus
from app.services.audit import AuditAction, record
from app.services.organisations import enforce_limit

logger = logging.getLogger(__name__)

DAILY_LIMIT: Final = 50
DAILY_LIMIT_PERIOD: Final = timedelta(days=1)
# A report still queued or being drawn after this long is failed when next read: drawing
# one takes seconds, so the worker that had it is gone.
STALE_AFTER: Final = timedelta(minutes=10)
PENDING: Final = (ReportStatus.QUEUED, ReportStatus.RENDERING)
# Snapshot fields that say when and for whom, not what: two reports that differ only in
# these show the same result.
_OCCASION: Final = ("generated_at", "requested_by")


@dataclass(frozen=True, slots=True)
class ReportSubject:
    """One final readiness result or one confirmed IQ assessment, already checked to be
    visible to the person asking, and where its audit events point."""

    subject_type: AdviceSubject
    assessment_id: uuid.UUID
    question_set_version: int
    target_type: str
    target_id: uuid.UUID


def file_key(report: Report) -> str:
    return f"reports/{report.organisation_id}/{report.id}.pdf"


def _lock(db: Session, ctx: OrgContext) -> None:
    """Serialise asking and version numbering in one organisation until the transaction
    ends, so two people asking at once get one report."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"reports:{ctx.organisation_id}"},
    )


def _of(ctx: OrgContext, subject: ReportSubject) -> Select[Report]:
    return select(Report).where(
        Report.organisation_id == ctx.organisation_id,
        Report.subject_type == subject.subject_type,
        Report.subject_id == subject.assessment_id,
    )


def _stale(report: Report, now: datetime) -> bool:
    """Queued too long without a worker, or drawn too long by one: timed from when it was
    queued, or from when a worker started drawing it."""
    if report.status is ReportStatus.QUEUED:
        return now - report.created_at > STALE_AFTER
    if report.status is ReportStatus.RENDERING:
        return now - (report.started_at or report.created_at) > STALE_AFTER
    return False


def _mark_failed(db: Session, report: Report, error: str) -> None:
    """Fail a report that is still queued or being drawn; leave a finished one alone. The
    caller commits."""
    db.execute(
        update(Report)
        .where(Report.id == report.id, Report.status.in_(PENDING))
        .values(status=ReportStatus.FAILED, error=error, finished_at=datetime.now(UTC))
    )
    db.refresh(report)


def fail(db: Session, report: Report, error: str) -> None:
    """Fail a report that is still queued or being drawn; leave a finished one alone.
    Commits."""
    _mark_failed(db, report, error)
    db.commit()


def file_intact(report: Report) -> bool:
    """The ready report's file is in storage and is the file that was stored."""
    if report.status is not ReportStatus.READY or report.file_key is None:
        return False
    try:
        data = get_storage().get(report.file_key)
    except FileNotFoundError:
        return False
    return hashlib.sha256(data).hexdigest() == report.file_sha256


def list_reports(db: Session, ctx: OrgContext, subject: ReportSubject) -> list[Report]:
    """The result's reports, newest first. Reports left pending by a lost worker are failed
    on the way. Commits."""
    reports = list(db.scalars(_of(ctx, subject).order_by(Report.version.desc())))
    now = datetime.now(UTC)
    for report in reports:
        if _stale(report, now):
            _mark_failed(db, report, "The report was not drawn in time.")
    db.commit()
    return reports


def _same_content(a: dict[str, Any], b: dict[str, Any]) -> bool:
    def content(snapshot: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in snapshot.items() if k not in _OCCASION}

    return content(a) == content(b)


def request(
    db: Session, ctx: OrgContext, subject: ReportSubject, snapshot: dict[str, Any]
) -> Report:
    """Ask for a report showing ``snapshot``. Returns the report that will show it: one
    already on its way, the newest ready one when it shows the same, or a new version.
    Commits, then queues the drawing."""
    # Imported here: the task module imports this one.
    from app.jobs.tasks.reports import render_report  # noqa: PLC0415

    _lock(db, ctx)
    now = datetime.now(UTC)
    newest = db.scalars(_of(ctx, subject).order_by(Report.version.desc()).limit(1)).first()
    if newest is not None and _stale(newest, now):
        # In this transaction, under the lock: whoever asks next sees it failed.
        _mark_failed(db, newest, "The report was not drawn in time.")
    if newest is not None and (
        newest.status in PENDING
        or (
            newest.status is ReportStatus.READY
            and _same_content(newest.snapshot, snapshot)
            # A ready report whose file is gone is made again, not handed back.
            and file_intact(newest)
        )
    ):
        db.commit()
        return newest
    enforce_limit(
        db,
        Report.created_at,
        Report.organisation_id == ctx.organisation_id,
        limit=DAILY_LIMIT,
        period=DAILY_LIMIT_PERIOD,
        rule="Your organisation has made as many PDF reports as are allowed in one day.",
    )
    version = (
        db.scalar(
            select(func.max(Report.version)).where(
                Report.organisation_id == ctx.organisation_id,
                Report.subject_type == subject.subject_type,
                Report.subject_id == subject.assessment_id,
            )
        )
        or 0
    ) + 1
    report = Report(
        organisation_id=ctx.organisation_id,
        subject_type=subject.subject_type,
        subject_id=subject.assessment_id,
        question_set_version=subject.question_set_version,
        version=version,
        status=ReportStatus.QUEUED,
        requested_by_user_id=ctx.user.id,
        template_version=int(snapshot["template_version"]),
        snapshot=snapshot,
        # Set here, not by the database: its clock stands still inside a transaction.
        created_at=now,
    )
    db.add(report)
    db.flush()
    record(
        db,
        AuditAction.REPORT_REQUESTED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type=subject.target_type,
        target_id=subject.target_id,
        # Which result and which version. Never any of its content.
        details={
            "subject": subject.subject_type.value,
            "assessment_id": str(subject.assessment_id),
            "question_set_version": subject.question_set_version,
            "version": version,
        },
    )
    db.commit()
    try:
        render_report.delay(str(report.id))
    except BrokerError:
        logger.exception("Could not queue report %s", report.id)
        fail(db, report, "The report could not be queued.")
    db.refresh(report)
    return report


def get_report(
    db: Session, ctx: OrgContext, subject: ReportSubject, report_id: uuid.UUID
) -> Report:
    """One report of the result; 404 when it is another result's or organisation's."""
    report = db.scalars(_of(ctx, subject).where(Report.id == report_id)).first()
    if report is None:
        raise AppError("not_found", "There is no such report.", 404)
    return report


def pdf_of(report: Report) -> bytes:
    """The report's PDF. 409 while it is not ready; 410 when its file is gone or is not the
    file that was stored."""
    if report.status is not ReportStatus.READY or report.file_key is None:
        raise AppError("report_not_ready", "This report is not ready to download.", 409)
    try:
        data = get_storage().get(report.file_key)
    except FileNotFoundError:
        data = b""
    if hashlib.sha256(data).hexdigest() != report.file_sha256:
        logger.error("Report %s: its file is missing or changed", report.id)
        raise AppError(
            "report_file_missing", "This report's file is no longer available. Make it again.", 410
        )
    return data


def requester_names(db: Session, reports: Sequence[Report]) -> dict[uuid.UUID, str]:
    ids = {r.requested_by_user_id for r in reports if r.requested_by_user_id is not None}
    if not ids:
        return {}
    return {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(ids)))}
