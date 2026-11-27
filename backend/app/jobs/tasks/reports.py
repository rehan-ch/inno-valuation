"""Draw PDF reports in the background (Phase 7, P7.03) and say when one is ready (P7.04).

The task receives the report id only. It claims the report (queued to rendering) under a
row lock, draws the PDF from the stored snapshot outside any lock, keeps the file, then
marks the report ready only if it is still the claim it made: a report failed meanwhile
(drawn too slowly, see ``services.reports.STALE_AFTER``) stays failed and its file is
removed. Idempotent: a report that is not queued, or that another worker is drawing, is
skipped.

The email goes to the person who asked, only while they can still see the result. It links
to the result's page and holds none of its content.
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from resend.exceptions import ResendError
from sqlalchemy import select, update

from app.core.permissions import Permission
from app.core.settings import get_settings
from app.core.storage import get_storage
from app.emails.backends import get_email_backend
from app.emails.messages import ReportEmail, render_report_ready
from app.jobs.celery_app import celery_app
from app.jobs.db import task_session
from app.models import Report, User
from app.models.enums import AdviceSubject, ReportStatus
from app.reports.render import render_pdf
from app.services import reports
from app.services.access import resolve_org_access

logger = logging.getLogger(__name__)

SKIPPED = "skipped"
SENT = "sent"


@celery_app.task(name="reports.render")
def render_report(report_id: str) -> str:
    with task_session() as db:
        report = db.scalars(
            select(Report)
            .where(Report.id == uuid.UUID(report_id))
            .with_for_update(skip_locked=True)
        ).first()
        if report is None or report.status is not ReportStatus.QUEUED:
            db.rollback()
            logger.info("Skipped report %s: gone, drawn or held by another worker", report_id)
            return SKIPPED
        started = datetime.now(UTC)
        report.status = ReportStatus.RENDERING
        report.started_at = started
        db.commit()

        try:
            pdf = render_pdf(report.snapshot)
        except Exception as error:  # any failure to draw fails the report
            logger.exception("Report %s could not be drawn", report_id)
            reports.fail(db, report, f"The PDF could not be drawn ({type(error).__name__}).")
            return report.status.value

        key = reports.file_key(report)
        storage = get_storage()
        storage.put(key, pdf.data)
        finished = db.execute(
            update(Report)
            .where(
                Report.id == report.id,
                Report.status == ReportStatus.RENDERING,
                Report.started_at == started,
            )
            .values(
                status=ReportStatus.READY,
                file_key=key,
                file_size=len(pdf.data),
                file_sha256=hashlib.sha256(pdf.data).hexdigest(),
                page_count=pdf.page_count,
                finished_at=datetime.now(UTC),
            )
        )
        db.commit()
        if finished.rowcount != 1:  # type: ignore[attr-defined]
            storage.delete(key)
            logger.info("Report %s was failed while it was drawn; its file is removed", report_id)
            return SKIPPED
    send_report_ready.delay(report_id)
    return ReportStatus.READY.value


def result_path(report: Report) -> str:
    """The frontend page of the report's result, where its reports are downloaded."""
    if report.subject_type is AdviceSubject.READINESS_RESULT:
        return f"/readiness/{report.subject_id}/result"
    idea_id = report.snapshot["assessment"]["idea_id"]
    return f"/ideas/{idea_id}/assessments/{report.subject_id}"


@celery_app.task(
    name="reports.send_ready",
    autoretry_for=(ResendError,),
    retry_backoff=True,
    max_retries=3,
)
def send_report_ready(report_id: str) -> str:
    with task_session() as db:
        report = db.get(Report, uuid.UUID(report_id))
        if report is None or report.status is not ReportStatus.READY:
            return SKIPPED
        user = db.get(User, report.requested_by_user_id) if report.requested_by_user_id else None
        if user is None or not user.is_active:
            return SKIPPED
        ctx = resolve_org_access(db, user, report.organisation_id)
        needed = (
            Permission.VIEW_ASSESSMENTS
            if report.subject_type is AdviceSubject.READINESS_RESULT
            else Permission.VIEW_IDEAS
        )
        if ctx is None or not ctx.can(needed):
            logger.info("Skipped the ready email for report %s: no access any more", report_id)
            return SKIPPED
        message = render_report_ready(
            to=user.email,
            origin=get_settings().frontend_origin,
            path=result_path(report),
            organisation_name=ctx.organisation.name,
            kind=(
                "readiness report"
                if report.subject_type is AdviceSubject.READINESS_RESULT
                else "idea report"
            ),
        )
    get_email_backend().send(
        message, idempotency_key=f"{ReportEmail.REPORT_READY.value}:{report_id}"
    )
    return SENT
