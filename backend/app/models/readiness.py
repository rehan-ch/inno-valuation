"""Readiness assessments: each person's answers, the agreed answers, the final result.

Three tables: assessments, responses and results. Answers are JSONB maps of
``{question_id: 1..5}``; the database checks every value is a whole number on the
readiness scale, and the service layer checks the ids against the question set.
A ``ReadinessResult`` row is written once when the assessment becomes ``final`` and
is never changed afterwards (service layer rule, proven by a test in P3.04).

Foreign key behaviour: everything under an assessment dies with it, and an
assessment dies with its organisation. A deleted participant takes their own
answers along; the agreed answers and the result survive with ``set_by`` /
``created_by`` becoming NULL. The consensus row remembers how many people had
submitted when agreeing began, so the result can still count them afterwards.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import Timestamps, UuidPrimaryKey
from app.models.accounts import Organisation, User
from app.models.enums import ReadinessStatus, enum_type


def _answers_1_to_5(column: str) -> CheckConstraint:
    """Every value in the JSONB map is a whole number 1 to 5 (spec 2.1).

    Enumerated values instead of a range: jsonpath comparisons with a non-number are
    unknown (never true), so a range check alone would let strings through, and 2.5
    must fail while 2 passes. Strict mode, because lax mode unwraps arrays and would
    let ``[3]`` pass as ``3``.
    """
    path = 'strict $.* ? (@.type() != "number" || @ != 1 && @ != 2 && @ != 3 && @ != 4 && @ != 5)'
    return CheckConstraint(f"NOT jsonb_path_exists({column}, '{path}')", name=f"{column}_1_to_5")


class ReadinessAssessment(UuidPrimaryKey, Timestamps, Base):
    __tablename__ = "readiness_assessments"
    __table_args__ = (
        # Also serves as the organisation_id index; listings are newest first.
        Index(
            "ix_readiness_assessments_organisation_id_created_at",
            "organisation_id",
            "created_at",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    question_set_version: Mapped[int]
    # A new assessment collects answers at once; ``draft`` is kept in the enum for old
    # clients but nothing creates one.
    status: Mapped[ReadinessStatus] = mapped_column(
        enum_type(ReadinessStatus, "readiness_status"),
        default=ReadinessStatus.COLLECTING,
        server_default=text("'collecting'"),
    )
    # The organisation's weights at finalising time, as validate_weights returns them.
    # They never change any score; they only order tied priorities (Amy Q2, Q23).
    weights_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    started_at: Mapped[datetime | None]
    finalised_at: Mapped[datetime | None]

    organisation: Mapped[Organisation] = relationship()
    responses: Mapped[list["ReadinessResponse"]] = relationship(back_populates="assessment")
    consensus: Mapped["ReadinessConsensus | None"] = relationship(back_populates="assessment")
    result: Mapped["ReadinessResult | None"] = relationship(back_populates="assessment")


class ReadinessResponse(UuidPrimaryKey, Timestamps, Base):
    """One person's own answers, saved as they go; ``submitted_at`` marks them done."""

    __tablename__ = "readiness_responses"
    __table_args__ = (
        UniqueConstraint("assessment_id", "user_id"),
        _answers_1_to_5("answers"),
        Index("ix_readiness_responses_organisation_id", "organisation_id"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("readiness_assessments.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    answers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    submitted_at: Mapped[datetime | None]

    assessment: Mapped[ReadinessAssessment] = relationship(back_populates="responses")
    user: Mapped[User] = relationship()


class ReadinessConsensus(UuidPrimaryKey, Timestamps, Base):
    """The facilitator's agreed answer per question (Amy Q5), with an optional note each."""

    __tablename__ = "readiness_consensus"
    __table_args__ = (
        UniqueConstraint("assessment_id"),
        _answers_1_to_5("answers"),
        CheckConstraint("participant_count >= 1", name="participant_count_positive"),
        Index("ix_readiness_consensus_organisation_id", "organisation_id"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("readiness_assessments.id", ondelete="CASCADE")
    )
    answers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    # {question_id: free-text note}; the facilitator's reasoning, never scored.
    notes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    # How many people had submitted when agreeing began. Fixed then, because a response
    # goes when its person is deleted and the result must still count them.
    participant_count: Mapped[int]
    set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    assessment: Mapped[ReadinessAssessment] = relationship(back_populates="consensus")


class ReadinessResult(UuidPrimaryKey, Base):
    """The scored outcome, written once when the assessment becomes final."""

    __tablename__ = "readiness_results"
    __table_args__ = (
        UniqueConstraint("assessment_id"),
        CheckConstraint("total >= 0 AND total <= 300", name="total_0_to_300"),
        CheckConstraint("participant_count >= 1", name="participant_count_positive"),
        Index("ix_readiness_results_organisation_id", "organisation_id"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("readiness_assessments.id", ondelete="CASCADE")
    )
    # {dimension key: score 0..25}, every dimension present, book order not implied.
    per_dimension: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # {category key: total}, as scoring.categories.readiness_categories returns.
    category_scores: Mapped[dict[str, Any]] = mapped_column(JSONB)
    total: Mapped[int]
    # How many people's submitted answers the agreed answers were set from.
    participant_count: Mapped[int]
    band_key: Mapped[str] = mapped_column(String(50))
    # The priority list as scored (lowest five, spec 7), already ordered.
    priorities: Mapped[list[Any]] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    assessment: Mapped[ReadinessAssessment] = relationship(back_populates="result")
