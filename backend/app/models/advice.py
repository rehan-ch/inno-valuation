"""AI advice that people act on (Phase 6): interpretations and recommendations.

Both are copied from a succeeded AI run and link back to it (``ai_run_id``), so every
sentence can be traced to the prompt, the model and the answer that produced it. The
subject is one final readiness result or one confirmed IQ assessment (``AdviceSubject``
plus the assessment's id), never both: the two scores are not mixed (spec 4).

Rows are never changed. Asking again writes a new ``version`` beside the old one; the
highest version is the current advice.

A recommendation keeps Amy's fixed next-step text (``fixed_text``, verbatim from the
question set, spec 8) in its own column, apart from the AI's tailored advice (``ai_json``).
``priority_rank`` is the engine's rank of the dimension (spec 7), never the AI's.

The gap actions (touchpoint 5) and the consultation suggestion (touchpoint 8) have no
table: they are their AI run, like a question explanation.
"""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import CreatedAt, UuidPrimaryKey
from app.models.enums import AdviceSubject, enum_type


class Interpretation(UuidPrimaryKey, CreatedAt, Base):
    """What a result means, in the AI's words (touchpoint 4). It holds no number."""

    __tablename__ = "interpretations"
    __table_args__ = (
        UniqueConstraint("ai_run_id"),
        UniqueConstraint("subject_type", "subject_id", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
        # Also the organisation_id index.
        Index("ix_interpretations_organisation_id_subject", "organisation_id", "subject_id"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    subject_type: Mapped[AdviceSubject] = mapped_column(enum_type(AdviceSubject, "subject_type"))
    subject_id: Mapped[uuid.UUID]
    question_set_version: Mapped[int]
    version: Mapped[int]
    # The overall summary: a list of short sentences.
    summary: Mapped[list[Any]] = mapped_column(JSONB)
    # [{dimension_key, meaning, strengths: [..], gaps: [..]}], every dimension once.
    per_dimension: Mapped[list[Any]] = mapped_column(JSONB)
    ai_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"))


class Recommendation(UuidPrimaryKey, CreatedAt, Base):
    """One priority dimension's recommendation (touchpoint 6): the book's fixed next steps
    beside the AI's initiatives, KPIs, timeline and resources."""

    __tablename__ = "recommendations"
    __table_args__ = (
        # Also the ai_run_id index.
        UniqueConstraint("ai_run_id", "dimension_key"),
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "version",
            "dimension_key",
            name="uq_recommendations_subject_version_dimension_key",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("priority_rank >= 1", name="priority_rank_positive"),
        # Also the organisation_id index.
        Index("ix_recommendations_organisation_id_subject", "organisation_id", "subject_id"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    subject_type: Mapped[AdviceSubject] = mapped_column(enum_type(AdviceSubject, "subject_type"))
    subject_id: Mapped[uuid.UUID]
    question_set_version: Mapped[int]
    version: Mapped[int]
    dimension_key: Mapped[str] = mapped_column(String(50))
    # The engine's rank among the priorities (1 is the most urgent), as stored on the result.
    priority_rank: Mapped[int]
    # Amy's next-step text for the dimension, verbatim from the question set.
    fixed_text: Mapped[str] = mapped_column(Text)
    # {initiatives: [..], kpis: [..], timeline: "..", resources: [..]}
    ai_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    ai_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"))
