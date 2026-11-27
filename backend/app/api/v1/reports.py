"""PDF reports of a final readiness result or of an idea's confirmed scores (Phase 7).

Listing and downloading need the permission to see the result (and, for a consultant,
only what a consultant may see); making a report needs ``reports.request``. Making one
returns at once with the report "queued"; poll the list until it is ready or failed.

The report shows what the result's page shows: the snapshot is built here from the very
payloads that page reads (``result_out``, ``assessment_out``, ``advice_out``), and the AI
advice only where the page would show it.
"""

import uuid
from datetime import UTC, datetime
from typing import Final

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.ai.client import is_offline
from app.api.v1.advice import advice_out
from app.api.v1.ideas import assessment_out
from app.api.v1.readiness import result_out
from app.core.deps import get_db, require_permission
from app.core.errors import AppError
from app.core.permissions import OrgContext, Permission
from app.models import Report
from app.models.enums import AdviceSubject, IqAssessmentStatus
from app.reports import snapshot
from app.schemas.reports import ReportOut, ReportsOut
from app.services import advice, ideas, readiness, reports
from app.services.reports import ReportSubject

router = APIRouter(tags=["reports"])

READINESS: Final = "/readiness/assessments/{assessment_id}/reports"
IQ: Final = "/ideas/{idea_id}/assessments/{assessment_id}/reports"


def _readiness_subject(db: Session, ctx: OrgContext, assessment_id: uuid.UUID) -> ReportSubject:
    """A final readiness result the caller may see; 404 otherwise."""
    assessment = readiness.get_assessment(db, ctx, assessment_id)
    if assessment.finalised_at is None or readiness.result_of(db, assessment) is None:
        raise AppError("not_found", "This assessment has no result yet.", 404)
    return ReportSubject(
        subject_type=AdviceSubject.READINESS_RESULT,
        assessment_id=assessment.id,
        question_set_version=assessment.question_set_version,
        target_type="readiness_assessment",
        target_id=assessment.id,
    )


def _iq_subject(
    db: Session, ctx: OrgContext, idea_id: uuid.UUID, assessment_id: uuid.UUID
) -> ReportSubject:
    """An idea's confirmed scores the caller may see; 404 otherwise."""
    idea = ideas.get_idea(db, ctx, idea_id)
    assessment = ideas.get_assessment(db, ctx, idea, assessment_id)
    if assessment.status is not IqAssessmentStatus.CONFIRMED:
        raise AppError("not_found", "These scores are not confirmed yet.", 404)
    return ReportSubject(
        subject_type=AdviceSubject.IQ_ASSESSMENT,
        assessment_id=assessment.id,
        question_set_version=assessment.question_set_version,
        target_type="idea",
        target_id=idea.id,
    )


def _report_out(report: Report, names: dict[uuid.UUID, str]) -> ReportOut:
    return ReportOut(
        id=report.id,
        version=report.version,
        status=report.status,
        question_set_version=report.question_set_version,
        requested_by_name=(
            names.get(report.requested_by_user_id) if report.requested_by_user_id else None
        ),
        created_at=report.created_at,
        finished_at=report.finished_at,
        file_size=report.file_size,
        page_count=report.page_count,
    )


def _reports_out(db: Session, ctx: OrgContext, subject: ReportSubject) -> ReportsOut:
    found = reports.list_reports(db, ctx, subject)
    names = reports.requester_names(db, found)
    return ReportsOut(
        subject=subject.subject_type,
        assessment_id=subject.assessment_id,
        can_request=ctx.can(Permission.REQUEST_REPORTS),
        reports=[_report_out(r, names) for r in found],
    )


def _pdf(report: Report) -> Response:
    kind = "readiness" if report.subject_type is AdviceSubject.READINESS_RESULT else "idea"
    made = report.created_at.astimezone(UTC).date().isoformat()
    return Response(
        content=reports.pdf_of(report),
        media_type="application/pdf",
        headers={
            # A fixed, ASCII name: nothing typed by a user goes into a header.
            "Content-Disposition": (
                f'attachment; filename="innovaluation-{kind}-report-{made}-v{report.version}.pdf"'
            ),
            "Cache-Control": "private, no-store",
        },
    )


# Readiness


@router.get(READINESS, response_model=ReportsOut, status_code=status.HTTP_200_OK)
def list_readiness_reports(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> ReportsOut:
    """The PDF reports of a final readiness result, newest first."""
    return _reports_out(db, ctx, _readiness_subject(db, ctx, assessment_id))


@router.post(READINESS, response_model=ReportsOut, status_code=status.HTTP_200_OK)
def request_readiness_report(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.REQUEST_REPORTS)),
    db: Session = Depends(get_db),
) -> ReportsOut:
    """Make a PDF report of a final readiness result. Returns at once; poll the GET until
    the newest report is ready or failed. Asking again while one is on its way, or when
    nothing has changed since the newest one, returns that one."""
    subject = _readiness_subject(db, ctx, assessment_id)
    assessment = readiness.get_assessment(db, ctx, assessment_id)
    shown = None
    if not is_offline():
        shown = advice_out(
            ctx, advice.get(db, ctx, advice.readiness_subject(db, ctx, assessment_id))
        )
    content = snapshot.readiness_snapshot(
        organisation=ctx.organisation.name,
        requested_by=ctx.user.name,
        generated_at=datetime.now(UTC),
        result=result_out(db, assessment),
        advice=shown,
    )
    reports.request(db, ctx, subject, content)
    return _reports_out(db, ctx, subject)


@router.get(
    READINESS + "/{report_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def download_readiness_report(
    assessment_id: uuid.UUID,
    report_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> Response:
    """The PDF of a ready report of a final readiness result."""
    subject = _readiness_subject(db, ctx, assessment_id)
    return _pdf(reports.get_report(db, ctx, subject, report_id))


# Ideas


@router.get(IQ, response_model=ReportsOut, status_code=status.HTTP_200_OK)
def list_iq_reports(
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_IDEAS)),
    db: Session = Depends(get_db),
) -> ReportsOut:
    """The PDF reports of an idea's confirmed scores, newest first."""
    return _reports_out(db, ctx, _iq_subject(db, ctx, idea_id, assessment_id))


@router.post(IQ, response_model=ReportsOut, status_code=status.HTTP_200_OK)
def request_iq_report(
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.REQUEST_REPORTS)),
    db: Session = Depends(get_db),
) -> ReportsOut:
    """Make a PDF report of an idea's confirmed scores. Returns at once; poll the GET until
    the newest report is ready or failed."""
    subject = _iq_subject(db, ctx, idea_id, assessment_id)
    idea = ideas.get_idea(db, ctx, idea_id)
    assessment = ideas.get_assessment(db, ctx, idea, assessment_id)
    shown = None
    if not is_offline():
        shown = advice_out(
            ctx, advice.get(db, ctx, advice.iq_subject(db, ctx, idea_id, assessment_id))
        )
    content = snapshot.iq_snapshot(
        organisation=ctx.organisation.name,
        requested_by=ctx.user.name,
        generated_at=datetime.now(UTC),
        idea=idea,
        assessment=assessment_out(db, ctx, idea, assessment),
        advice=shown,
    )
    reports.request(db, ctx, subject, content)
    return _reports_out(db, ctx, subject)


@router.get(
    IQ + "/{report_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def download_iq_report(
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    report_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_IDEAS)),
    db: Session = Depends(get_db),
) -> Response:
    """The PDF of a ready report of an idea's confirmed scores."""
    subject = _iq_subject(db, ctx, idea_id, assessment_id)
    return _pdf(reports.get_report(db, ctx, subject, report_id))
