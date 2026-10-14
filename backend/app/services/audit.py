"""Write audit events. Details never hold secrets, passwords, raw tokens, idea text, answers
or company details: callers pass only ids, field names and short reason codes."""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent, User


class AuditAction(StrEnum):
    SIGNED_UP = "user.signed_up"
    SIGN_UP_EXISTING_EMAIL = "user.sign_up_existing_email"
    SIGNED_IN = "user.signed_in"
    SIGN_IN_FAILED = "user.sign_in_failed"
    SIGNED_OUT = "user.signed_out"
    EMAIL_VERIFIED = "user.email_verified"
    PASSWORD_RESET_REQUESTED = "user.password_reset_requested"  # noqa: S105
    PASSWORD_RESET = "user.password_reset"  # noqa: S105
    PASSWORD_CHANGED = "user.password_changed"  # noqa: S105
    USER_DISABLED = "user.disabled"
    ORGANISATION_CREATED = "organisation.created"
    ORGANISATION_UPDATED = "organisation.updated"
    MEMBER_INVITED = "member.invited"
    INVITATION_REVOKED = "member.invitation_revoked"
    INVITATION_ACCEPTED = "member.invitation_accepted"
    MEMBER_ROLE_CHANGED = "member.role_changed"
    MEMBER_REMOVED = "member.removed"
    CONSULTANT_ACCESS_GRANTED = "consultant.access_granted"
    CONSULTANT_ACCESS_CHANGED = "consultant.access_changed"
    CONSULTANT_ACCESS_REVOKED = "consultant.access_revoked"
    CONSULTANT_ACCESS_ACCEPTED = "consultant.access_accepted"


def record(
    db: Session,
    action: AuditAction,
    *,
    actor: User | None,
    organisation_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an audit event to the session. The caller commits."""
    event = AuditEvent(
        action=action.value,
        actor_user_id=actor.id if actor else None,
        organisation_id=organisation_id,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )
    db.add(event)
    db.flush()
    return event
