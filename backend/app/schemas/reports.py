"""PDF reports of a result (Phase 7)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AdviceSubject, ReportStatus


class ReportOut(BaseModel):
    """One report of a result. ``status`` is queued or rendering while it is being drawn,
    then ready (download it) or failed (make it again)."""

    id: uuid.UUID
    version: int
    status: ReportStatus
    question_set_version: int
    requested_by_name: str | None
    created_at: datetime
    finished_at: datetime | None
    # Set once ready: the PDF's size in bytes and its number of pages.
    file_size: int | None
    page_count: int | None


class ReportsOut(BaseModel):
    """Every report of one result, newest first."""

    subject: AdviceSubject
    assessment_id: uuid.UUID
    # The caller may make a report of this result.
    can_request: bool
    reports: list[ReportOut]
