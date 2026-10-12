"""Columns shared by every table: a UUID primary key and UTC timestamps."""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class UuidPrimaryKey:
    # UUIDs, not sequential integers, so record IDs in URLs cannot be guessed or counted.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, sort_order=-10)


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), sort_order=10)


class Timestamps(CreatedAt):
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), sort_order=11
    )
