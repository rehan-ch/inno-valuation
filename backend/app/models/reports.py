"""PDF reports (Phase 7, P7.01): one row per report asked for, with everything it shows.

A report is about one final readiness result or one confirmed IQ assessment
(``AdviceSubject`` plus the assessment's id), never both: the two scores are not mixed
(spec 4). ``snapshot`` holds what the PDF shows, copied from what the app showed for the
same result when the report was asked for, so a report can always be drawn again exactly
as it was, whatever changes later (targets, names, advice). ``template_version`` names the
layout it was drawn with.

Rows are never changed once ready or failed. Asking again writes a new ``version`` beside
the old one; every version stays downloadable.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import CreatedAt, UuidPrimaryKey
from app.models.enums import AdviceSubject, ReportStatus, enum_type


class Report(UuidPrimaryKey, CreatedAt, Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("subject_type", "subject_id", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("template_version >= 1", name="template_version_positive"),
        # A ready report has its file; no other report has one.
        CheckConstraint(
            "(status = 'ready') = (file_key IS NOT NULL AND file_size IS NOT NULL"
            " AND file_sha256 IS NOT NULL)",
            name="file_when_ready",
        ),
        CheckConstraint("file_size IS NULL OR file_size > 0", name="file_size_positive"),
        # Also the organisation_id index. Lists a subject's reports, newest first.
        Index("ix_reports_organisation_id_subject", "organisation_id", "subject_id", "version"),
        # Counts an organisation's reports over the last day (the abuse limit).
        Index("ix_reports_organisation_id_created_at", "organisation_id", "created_at"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    subject_type: Mapped[AdviceSubject] = mapped_column(enum_type(AdviceSubject, "subject_type"))
    subject_id: Mapped[uuid.UUID]
    question_set_version: Mapped[int]
    version: Mapped[int]
    status: Mapped[ReportStatus] = mapped_column(
        enum_type(ReportStatus, "status"), default=ReportStatus.QUEUED
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    template_version: Mapped[int]
    # Everything the PDF shows, as the app showed it (see app/reports/snapshot.py).
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)

    # The PDF in file storage, once ready: its key, size in bytes, SHA-256 and pages.
    file_key: Mapped[str | None] = mapped_column(String(200))
    file_size: Mapped[int | None]
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None]
    # Why drawing it failed, for the log. Never shown to users; holds no user text.
    error: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
