"""Decide whether a "resend verification" or "forgot password" request gets an email.

Runs in the Celery worker, not in the request. The request only looks the email up, commits
and queues one task, the same work whether or not the account exists, so response timing
does not reveal registered emails. Everything that differs (token rows, audit events) happens
here.
"""

from sqlalchemy.orm import Session

from app.emails.messages import AccountEmail
from app.models import User, UserToken
from app.models.enums import UserTokenPurpose
from app.services import user_tokens
from app.services.audit import AuditAction, record

REQUESTABLE = frozenset({AccountEmail.VERIFY_EMAIL, AccountEmail.RESET_PASSWORD})


def issue_requested_token(db: Session, kind: AccountEmail, user: User) -> UserToken | None:
    """The token to email for this request, or None when nothing should be sent. Commits."""
    if kind not in REQUESTABLE:
        raise ValueError(f"{kind.value} cannot be requested")
    token: UserToken | None = None
    if kind is AccountEmail.VERIFY_EMAIL:
        if user.is_active and user.email_verified_at is None:
            # A contested account keeps requiring a password (see user_tokens.issue).
            token = user_tokens.issue(db, user, UserTokenPurpose.VERIFY_EMAIL)
    elif user.is_active:
        token = user_tokens.issue(db, user, UserTokenPurpose.RESET_PASSWORD)
        if token is not None:
            record(
                db,
                AuditAction.PASSWORD_RESET_REQUESTED,
                actor=user,
                target_type="user",
                target_id=user.id,
            )
    db.commit()
    return token
