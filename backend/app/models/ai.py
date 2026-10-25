"""The AI run log: one row per AI result, with everything needed to trace it.

Every AI output is stored next to the prompt that produced it, the model, the raw response
and the token use (CLAUDE.md rule 7, docs/methodology/ai-touchpoints.md "What is stored").
The subject is a ``subject_type`` plus a ``subject_id`` string, with no ORM polymorphism:
for "explain a question" it is ``readiness_question`` and ``<version>:<question id>``.

A run is written queued with its prompts already rendered, so the row holds exactly what
was sent. Only the AI task moves it on; a finished run (succeeded or failed) never
changes again. The validated output is ``response_json``; ``response_raw`` keeps the
model's last answer as it came, including one that failed the check.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import CreatedAt, UuidPrimaryKey
from app.models.enums import AiRunStatus, AiTouchpoint, enum_type


class AiRun(UuidPrimaryKey, CreatedAt, Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        # Also serves as the organisation_id index. Finds a subject's latest run.
        Index(
            "ix_ai_runs_organisation_id_subject",
            "organisation_id",
            "touchpoint",
            "subject_type",
            "subject_id",
            "created_at",
        ),
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND attempts >= 0", name="counts_positive"
        ),
        CheckConstraint("cost_micro_usd >= 0", name="cost_positive"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    touchpoint: Mapped[AiTouchpoint] = mapped_column(
        enum_type(AiTouchpoint, "touchpoint", length=50)
    )
    subject_type: Mapped[str] = mapped_column(String(50))
    subject_id: Mapped[str] = mapped_column(String(200))
    status: Mapped[AiRunStatus] = mapped_column(
        enum_type(AiRunStatus, "status"), default=AiRunStatus.QUEUED
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # What was asked: the model and settings from config/ai.yml, and the prompts as sent.
    model: Mapped[str] = mapped_column(String(100))
    effort: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(50))
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt: Mapped[str] = mapped_column(Text)

    # What came back. ``response_model`` is the model that answered, as the API reports
    # it (a refusal fallback can change it); "offline" for the development stand-in.
    response_model: Mapped[str | None] = mapped_column(String(100))
    response_raw: Mapped[str | None] = mapped_column(Text)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    stop_reason: Mapped[str | None] = mapped_column(String(50))

    # Use across every attempt (the first answer plus at most one retry).
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    input_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # Millionths of a US dollar at the list prices in config/ai.yml. Never a float.
    cost_micro_usd: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
    # The API's request id for each call, in order, to trace a call with the provider.
    provider_request_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    # Why the run failed, for the log. Never shown to users; holds no user text.
    error: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
