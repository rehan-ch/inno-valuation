"""Ideas and their IQ assessments (spec 3, 5, 7; Amy Q1, Q2, Q7).

Three tables. An ``Idea`` is what a team wants to score. An ``IqAssessment`` is one
scoring of it: the AI proposes 12 scores (``AiRun``), the idea owner confirms or changes
them, and the engine computes the IQ, levels, category scores, priorities and Value for
Money once, at confirmation. A confirmed assessment never changes; re-assessing creates a
new one and the old one stays for history (spec 9). ``IqDimensionScore`` keeps the AI's
proposal and the owner's final score side by side per dimension, so every change is
traceable (Amy Q1).

Money is stored in whole minor units (cents) with its ISO 4217 code, never as a float.
The investment and currency are copied onto the assessment when it is confirmed, so the
Value for Money shown always matches the figures it was computed from.

Foreign key behaviour: assessments and scores die with their idea, ideas with their
organisation. People become NULL ("created by", "requested by", "confirmed by",
"reviewed by") so the records survive their authors.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import CreatedAt, Timestamps, UuidPrimaryKey
from app.models.accounts import Organisation
from app.models.enums import IdeaStage, IdeaStatus, IqAssessmentStatus, enum_type


class Idea(UuidPrimaryKey, Timestamps, Base):
    __tablename__ = "ideas"
    __table_args__ = (
        CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        CheckConstraint(
            "investment_minor IS NULL OR investment_minor >= 0", name="investment_positive"
        ),
        CheckConstraint(
            "expected_value_minor IS NULL OR expected_value_minor >= 0",
            name="expected_value_positive",
        ),
        # Also serves as the organisation_id index; listings are newest first.
        Index("ix_ideas_organisation_id_created_at", "organisation_id", "created_at"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    target_market: Mapped[str | None] = mapped_column(Text)
    uniqueness: Mapped[str | None] = mapped_column(Text)
    team: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[IdeaStage] = mapped_column(
        enum_type(IdeaStage, "idea_stage"), default=IdeaStage.IDEA
    )
    # The total planned or known investment in the idea (Amy Q7), in minor units.
    investment_minor: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3))
    expected_value_minor: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[IdeaStatus] = mapped_column(
        enum_type(IdeaStatus, "idea_status"),
        default=IdeaStatus.DRAFT,
        server_default=text("'draft'"),
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    archived_at: Mapped[datetime | None]

    organisation: Mapped[Organisation] = relationship()
    assessments: Mapped[list["IqAssessment"]] = relationship(back_populates="idea")


class IqAssessment(UuidPrimaryKey, CreatedAt, Base):
    """One scoring of an idea: proposed by the AI, confirmed by the owner, computed once."""

    __tablename__ = "iq_assessments"
    __table_args__ = (
        Index("ix_iq_assessments_organisation_id", "organisation_id"),
        Index("ix_iq_assessments_idea_id_created_at", "idea_id", "created_at"),
        CheckConstraint("iq IS NULL OR (iq >= 0 AND iq <= 100)", name="iq_0_to_100"),
        CheckConstraint(
            "investment_minor IS NULL OR investment_minor >= 0", name="investment_positive"
        ),
        CheckConstraint("vfm_per_point IS NULL OR vfm_per_point >= 0", name="vfm_positive"),
        CheckConstraint(
            "(status = 'confirmed') = (confirmed_at IS NOT NULL AND iq IS NOT NULL)",
            name="confirmed_is_scored",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    idea_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ideas.id", ondelete="CASCADE"))
    question_set_version: Mapped[int]
    status: Mapped[IqAssessmentStatus] = mapped_column(
        enum_type(IqAssessmentStatus, "iq_assessment_status"),
        default=IqAssessmentStatus.PROPOSED,
        server_default=text("'proposed'"),
    )
    # The run that proposed the scores (touchpoint 3). Its status says whether the proposal
    # is still on its way, ready, or failed.
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_runs.id", ondelete="SET NULL"), index=True
    )
    # The organisation's weights at confirmation, as validate_weights returns them. They
    # never change the IQ; they only order tied priorities (Amy Q2, Q23).
    weights_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Written once, at confirmation, by the scoring engine (spec 3.2, 3.6, 7, 5.1).
    iq: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    # {category key: "70.0"}: decimal strings, so no float ever touches a score.
    category_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # [{"rank", "key", "score"}], lowest five, already ordered (spec 7).
    priorities: Mapped[list[Any] | None] = mapped_column(JSONB)
    # The idea's investment and currency as they were at confirmation (Amy Q7).
    investment_minor: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(CHAR(3))
    # Currency per innovation point, 2 decimals; NULL when it cannot be worked out.
    vfm_per_point: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    confirmed_at: Mapped[datetime | None]

    idea: Mapped[Idea] = relationship(back_populates="assessments")
    scores: Mapped[list["IqDimensionScore"]] = relationship(back_populates="assessment")


class IqDimensionScore(UuidPrimaryKey, Timestamps, Base):
    """One dimension of one assessment: the AI's proposal and the owner's final score.

    ``proposed_*`` is copied from the AI run once it succeeds and never changes.
    ``final_score`` is the owner's choice (the proposal, unless they change it); ``note`` is
    their reason or comment. ``level_key`` is set by the engine at confirmation (spec 3.1).
    """

    __tablename__ = "iq_dimension_scores"
    __table_args__ = (
        UniqueConstraint("assessment_id", "dimension_key"),
        CheckConstraint(
            "proposed_score IS NULL OR (proposed_score >= 1 AND proposed_score <= 10)",
            name="proposed_score_1_to_10",
        ),
        CheckConstraint(
            "final_score IS NULL OR (final_score >= 1 AND final_score <= 10)",
            name="final_score_1_to_10",
        ),
        CheckConstraint(
            "proposed_confidence IS NULL OR "
            "(proposed_confidence >= 0 AND proposed_confidence <= 1)",
            name="confidence_0_to_1",
        ),
        Index("ix_iq_dimension_scores_organisation_id", "organisation_id"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("iq_assessments.id", ondelete="CASCADE")
    )
    dimension_key: Mapped[str] = mapped_column(String(50))
    proposed_score: Mapped[int | None]
    # The AI's 2 to 4 sentences, as a JSON list, quoting the idea.
    proposed_rationale: Mapped[list[Any] | None] = mapped_column(JSONB)
    proposed_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    final_score: Mapped[int | None]
    level_key: Mapped[str | None] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    assessment: Mapped[IqAssessment] = relationship(back_populates="scores")
