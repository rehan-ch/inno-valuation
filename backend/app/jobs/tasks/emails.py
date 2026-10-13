"""Send account emails (verify email, reset password, already registered).

The task receives ids only: the email kind, the user id and a reference id (the
``user_tokens`` row for link emails, the audit event for the "already registered" notice).
It re-loads the rows and rebuilds the link from the token row id and the secret key, so the
raw token never travels through the broker. Account emails belong to a user, not to an
organisation, so there is no organisation to re-check.

Idempotent: a token email is sent only while its token is still usable, and the reference
id is the provider's idempotency key, so a re-delivered task does not send twice.

Links put the token in the URL fragment (``#token=...``), which browsers never send to a
server, so it stays out of server logs and Referer headers.
"""

import logging
import uuid

from resend.exceptions import ResendError
from sqlalchemy.orm import Session

from app.core.security import user_token_value
from app.core.settings import get_settings
from app.emails.backends import get_email_backend
from app.emails.messages import (
    AccountEmail,
    EmailMessage,
    render_already_registered,
    render_token_email,
)
from app.jobs.celery_app import celery_app
from app.jobs.db import task_session
from app.models import AuditEvent, User, UserToken
from app.models.enums import UserTokenPurpose
from app.services import account_emails, user_tokens
from app.services.audit import AuditAction

logger = logging.getLogger(__name__)

TOKEN_PURPOSES = {
    AccountEmail.VERIFY_EMAIL: UserTokenPurpose.VERIFY_EMAIL,
    AccountEmail.RESET_PASSWORD: UserTokenPurpose.RESET_PASSWORD,
}

SENT = "sent"
SKIPPED = "skipped"


@celery_app.task(
    name="emails.send_account_email",
    autoretry_for=(ResendError,),
    retry_backoff=True,
    max_retries=3,
)
def send_account_email(kind: str, user_id: str, ref_id: str) -> str:
    email_kind = AccountEmail(kind)
    with task_session() as db:
        user = db.get(User, uuid.UUID(user_id))
        if user is None or not user.is_active:
            logger.info("Skipped %s email: user %s is gone or disabled", kind, user_id)
            return SKIPPED
        message = _build(db, email_kind, user, uuid.UUID(ref_id))
        if message is None:
            logger.info("Skipped %s email for user %s: reference no longer valid", kind, user_id)
            return SKIPPED
    get_email_backend().send(message, idempotency_key=f"{kind}:{ref_id}")
    logger.info("Sent %s email for user %s", kind, user_id)
    return SENT


@celery_app.task(name="emails.request_account_email")
def request_account_email(kind: str, user_id: str | None) -> str:
    """Resend verification or forgot password, decided in the worker.

    The request queues this task for every email, known or not (``user_id`` is None when no
    account matched), so both paths cost the request the same. Idempotent: a re-delivered
    task hits the per-user rate limit and sends nothing more.
    """
    email_kind = AccountEmail(kind)
    if user_id is None:
        return SKIPPED
    with task_session() as db:
        user = db.get(User, uuid.UUID(user_id))
        if user is None:
            return SKIPPED
        token = account_emails.issue_requested_token(db, email_kind, user)
        if token is None:
            logger.info("No %s email for user %s (not eligible or rate limited)", kind, user_id)
            return SKIPPED
        token_id = str(token.id)
    # Same worker, same process: send now rather than queueing a second task.
    result: str = send_account_email(kind, user_id, token_id)
    return result


def _build(db: Session, kind: AccountEmail, user: User, ref_id: uuid.UUID) -> EmailMessage | None:
    origin = get_settings().frontend_origin
    if kind is AccountEmail.ALREADY_REGISTERED:
        # The reference is the audit event of the sign-up attempt, re-checked like a token.
        event = db.get(AuditEvent, ref_id)
        if (
            event is None
            or event.action != AuditAction.SIGN_UP_EXISTING_EMAIL.value
            or event.actor_user_id != user.id
        ):
            return None
        return render_already_registered(to=user.email, origin=origin)
    purpose = TOKEN_PURPOSES[kind]
    token = db.get(UserToken, ref_id)
    if (
        token is None
        or token.user_id != user.id
        or token.purpose is not purpose
        or not user_tokens.is_usable(token)
    ):
        return None
    return render_token_email(
        kind,
        to=user.email,
        origin=origin,
        token=user_token_value(token.id),
        expires_in=user_tokens.TOKEN_LIFETIMES[purpose],
    )
