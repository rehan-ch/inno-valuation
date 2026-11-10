"""Targets per dimension (spec 6; where targets can be set is PROVISIONAL, open-questions Q8).

One row per change and per scale: the newest row of a scale holds the organisation's
current targets on it, the older rows are the history. No row means no targets. Readiness
targets (5 to 25) and IQ targets (1 to 10) are separate rows and are never mixed (spec 4).
A target changes no score; the gap (target minus current) is worked out by the engine.

The database checks that every value is a number; the service layer validates the range
and the dimension keys with the engine.
"""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import CreatedAt, UuidPrimaryKey
from app.models.enums import TargetScale, enum_type


class DimensionTargets(UuidPrimaryKey, CreatedAt, Base):
    __tablename__ = "dimension_targets"
    __table_args__ = (
        # Strict mode, so an array value fails too.
        CheckConstraint(
            "NOT jsonb_path_exists(targets, 'strict $.* ? (@.type() != \"number\")')",
            name="targets_are_numbers",
        ),
        # Also the organisation_id index.
        Index(
            "ix_dimension_targets_organisation_id_scale_created_at",
            "organisation_id",
            "scale",
            "created_at",
        ),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    scale: Mapped[TargetScale] = mapped_column(enum_type(TargetScale, "target_scale"))
    question_set_version: Mapped[int]
    # {dimension key: target}; only the dimensions that have a target.
    targets: Mapped[dict[str, Any]] = mapped_column(JSONB)
    set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
