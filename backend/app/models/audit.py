"""Audit trail of security-relevant actions (sign-in, invitations, role changes, grants).

Rows are kept when the actor is deleted (``actor_user_id`` becomes NULL). An organisation
with audit events cannot be hard-deleted (RESTRICT): organisations are archived instead,
and a deliberate erase must remove its audit events first.

``details`` never holds secrets, passwords, tokens, idea text, answers or company details.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import CreatedAt, UuidPrimaryKey


class AuditEvent(UuidPrimaryKey, CreatedAt, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        # Also serves as the organisation_id index.
        Index("ix_audit_events_organisation_id_created_at", "organisation_id", "created_at"),
    )

    # NULL for events outside any organisation, such as signing in.
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisations.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[uuid.UUID | None]
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
