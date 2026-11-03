"""Dimension importance (client weights, spec 3.4 and 7).

One row per change: the newest row is the organisation's current weights, the older rows
are its history. No row means every dimension counts equally. Weights never change a score
or the IQ (Amy Q2); they only order tied priorities (PROVISIONAL, open-questions Q23).

Values are stored as decimal strings, as ``validate_weights`` returns them, so no float ever
touches a weight. The database checks that every value is a string; the service layer
validates the numbers.
"""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import CreatedAt, UuidPrimaryKey


class DimensionWeights(UuidPrimaryKey, CreatedAt, Base):
    __tablename__ = "dimension_weights"
    __table_args__ = (
        # Strict mode, so an array value fails too. Also the organisation_id index.
        CheckConstraint(
            "NOT jsonb_path_exists(weights, 'strict $.* ? (@.type() != \"string\")')",
            name="weights_are_strings",
        ),
        Index("ix_dimension_weights_organisation_id_created_at", "organisation_id", "created_at"),
    )

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE")
    )
    question_set_version: Mapped[int]
    # {dimension key: "2.5"}, every dimension of the question set, in book order.
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB)
    set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
