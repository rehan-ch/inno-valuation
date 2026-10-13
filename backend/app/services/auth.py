"""Email and password accounts: sign up, verify email, sign in, reset and change password.

No function here reveals whether an email is registered: sign up, resend verification and
forgot password answer the same way for every email, and a failed sign-in gives one
generic error. Only someone who knows the right password learns that the email is not
verified yet or that the account is disabled.

Emails are queued after the commit, so the task always finds the rows it needs. Resend
verification and forgot password do only a lookup, a commit and one queued task in the
request, whatever the email; the worker decides whether anything is sent.

Pre-registration takeover: someone may sign up with another person's email, before or
after them. A repeat sign-up for a still unverified account never carries a password and
changes nothing; its link is marked ``requires_password``, and verifying with it needs a
new password chosen at that moment, which replaces the stored one. Once contested, every
later link needs a password too, until the email is verified. So only someone who reads
the inbox can set the password that survives verification. A first sign-up's link stays
one click and keeps the password chosen at sign-up.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.emails import normalise_email
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.core.settings import get_settings
from app.emails.messages import AccountEmail
from app.jobs.tasks.emails import request_account_email, send_account_email
from app.models import AuditEvent, Membership, Organisation, User
from app.models.enums import OrganisationStatus, UserTokenPurpose
from app.services import sign_in_throttle, user_tokens
from app.services.audit import AuditAction, record

logger = logging.getLogger(__name__)

# PROVISIONAL: see open-questions Q14. Email and password sign-in is on (the default is
# "both"); Google sign-in is added next to it. Turning this off refuses sign up and sign in
# with a password.
PASSWORD_SIGN_IN_ENABLED: Final = True

# At most one "you already have an account" email per user in this time.
ALREADY_REGISTERED_COOLDOWN: Final = timedelta(hours=1)


@dataclass(frozen=True)
class SignInResult:
    user: User
    active_org_id: uuid.UUID | None


def _invalid_credentials() -> AppError:
    return AppError("invalid_credentials", "The email or password is not correct.", 401)


def _too_many_attempts() -> AppError:
    return AppError(
        "too_many_attempts",
        "Too many attempts. Wait 15 minutes, or reset your password.",
        429,
    )


def _require_password_sign_in() -> None:
    if not PASSWORD_SIGN_IN_ENABLED:
        raise AppError("password_sign_in_disabled", "Sign in with Google instead.", 403)


def _find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalise_email(email)))


def _queue_email(kind: AccountEmail, user_id: uuid.UUID, ref_id: uuid.UUID) -> None:
    try:
        send_account_email.delay(kind.value, str(user_id), str(ref_id))
    except BrokerError:
        # The account change is already saved; the user can ask for the email again.
        logger.exception("Could not queue the %s email for user %s", kind.value, user_id)


def _queue_request(kind: AccountEmail, user: User | None) -> None:
    try:
        request_account_email.delay(kind.value, str(user.id) if user else None)
    except BrokerError:
        logger.exception("Could not queue a %s request", kind.value)


# Sign up and email verification


def sign_up(db: Session, *, email: str, name: str, password: str) -> None:
    """Create an account and email a verification link. Same outcome for a known email.

    For a known, verified email nothing changes and the owner gets an "already registered"
    notice. For a known, unverified email nothing changes either: the submitted password is
    discarded and a new verification link that requires choosing a password is sent
    (``SIGN_UP_LIMIT`` per hour). The password is hashed in every case so the response
    time does not reveal which path ran.
    """
    _require_password_sign_in()
    email = normalise_email(email)
    password_hash = hash_password(password)
    existing = _find_user(db, email)
    if existing is None:
        settings = get_settings()
        user = User(
            email=email,
            name=name,
            password_hash=password_hash,
            terms_accepted_at=datetime.now(UTC),
            terms_version=settings.terms_version,
        )
        try:
            with db.begin_nested():
                db.add(user)
                db.flush()
        except IntegrityError:
            # Someone signed up with this email a moment ago. Treat it as a known email.
            existing = _find_user(db, email)
            if existing is None:
                raise
        else:
            record(db, AuditAction.SIGNED_UP, actor=user, target_type="user", target_id=user.id)
            token = user_tokens.issue(db, user, UserTokenPurpose.VERIFY_EMAIL)
            db.commit()
            if token is not None:
                _queue_email(AccountEmail.VERIFY_EMAIL, user.id, token.id)
            return
    _sign_up_known_email(db, existing)


def _sign_up_known_email(db: Session, user: User) -> None:
    if not user.is_active:
        db.commit()  # same work as the other paths
        return
    if user.email_verified_at is None:
        token = user_tokens.issue(
            db,
            user,
            UserTokenPurpose.VERIFY_EMAIL,
            requires_password=True,
            limit=user_tokens.SIGN_UP_LIMIT,
        )
        db.commit()
        if token is not None:
            _queue_email(AccountEmail.VERIFY_EMAIL, user.id, token.id)
        return
    recent = db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.actor_user_id == user.id,
            AuditEvent.action == AuditAction.SIGN_UP_EXISTING_EMAIL.value,
            AuditEvent.created_at > datetime.now(UTC) - ALREADY_REGISTERED_COOLDOWN,
        )
    )
    event = record(
        db, AuditAction.SIGN_UP_EXISTING_EMAIL, actor=user, target_type="user", target_id=user.id
    )
    db.commit()
    if not recent:
        _queue_email(AccountEmail.ALREADY_REGISTERED, user.id, event.id)


def resend_verification(db: Session, *, email: str) -> None:
    """Queue a new verification link; the worker sends it only to an unverified account."""
    user = _find_user(db, email)
    db.commit()
    _queue_request(AccountEmail.VERIFY_EMAIL, user)


def verify_email(db: Session, *, token: str, password: str | None = None) -> None:
    """Mark the email verified.

    A link with ``requires_password`` (contested sign-up) needs ``password``: without it
    this raises 400 ``password_required`` and leaves the link usable, so the page can ask
    for one and resubmit. With it, the password replaces whatever the account had. Any
    password sent with a one-click link is ignored: that link keeps the sign-up password.
    Verifying ends every session and clears the sign-in lock.
    """
    found = user_tokens.find_usable(db, token, UserTokenPurpose.VERIFY_EMAIL)
    if found is None:
        raise AppError("invalid_token", "This link is not valid or has expired.", 400)
    if found.requires_password and password is None:
        # Nothing is written, so the link stays usable; the row lock ends with the request.
        raise AppError(
            "password_required", "Choose a password to finish setting up your account.", 400
        )
    user_tokens.mark_used(db, found)
    user = found.user
    if user.email_verified_at is None:
        if found.requires_password and password is not None:
            user.password_hash = hash_password(password)
        user.email_verified_at = datetime.now(UTC)
        user.session_version += 1
        sign_in_throttle.clear(db, user.email)
        record(db, AuditAction.EMAIL_VERIFIED, actor=user, target_type="user", target_id=user.id)
    db.commit()


# Sign in and sign out


def sign_in(db: Session, *, email: str, password: str) -> SignInResult:
    _require_password_sign_in()
    email = normalise_email(email)
    user = _find_user(db, email)

    # Count the attempt before checking the password, then commit to release the row lock
    # during the slow hash check (see app.services.sign_in_throttle).
    attempt = sign_in_throttle.begin_attempt(db, email)
    if not attempt.allowed:
        if attempt.newly_locked:
            _record_failure(db, user, "locked")
        db.commit()
        raise _too_many_attempts()
    db.commit()

    check = verify_password(user.password_hash if user else None, password)
    if user is None or not check.ok:
        newly_locked = sign_in_throttle.attempt_failed(db, email)
        _record_failure(db, user, "locked" if newly_locked else "invalid_credentials")
        db.commit()
        raise _too_many_attempts() if newly_locked else _invalid_credentials()

    # The right password: forget the attempts whatever happens next.
    sign_in_throttle.clear(db, email)
    if not user.is_active:
        _record_failure(db, user, "disabled")
        db.commit()
        raise AppError("account_disabled", "This account is disabled.", 403)
    if user.email_verified_at is None:
        _record_failure(db, user, "email_not_verified")
        db.commit()
        raise AppError(
            "email_not_verified", "Please confirm your email first. Check your inbox.", 403
        )

    if check.needs_rehash:
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    record(db, AuditAction.SIGNED_IN, actor=user, target_type="user", target_id=user.id)
    db.commit()
    return SignInResult(user=user, active_org_id=_default_org(db, user))


def _record_failure(db: Session, user: User | None, reason: str) -> None:
    """Audit a failed sign-in for an existing account. Unknown emails leave no row at all,
    so guessing cannot fill the table; the actor id identifies the account, so no email is
    stored. Throttled attempts are audited once, when the lock starts."""
    if user is None:
        return
    record(
        db,
        AuditAction.SIGN_IN_FAILED,
        actor=user,
        target_type="user",
        target_id=user.id,
        details={"reason": reason},
    )


def _default_org(db: Session, user: User) -> uuid.UUID | None:
    """The organisation to start in: the only one, if the user belongs to exactly one and
    it is not archived."""
    org_ids = db.scalars(
        select(Membership.organisation_id).where(Membership.user_id == user.id).limit(2)
    ).all()
    if len(org_ids) != 1:
        return None
    organisation = db.get(Organisation, org_ids[0])
    if organisation is None or organisation.status is OrganisationStatus.ARCHIVED:
        return None
    return org_ids[0]


def record_sign_out(db: Session, user: User) -> None:
    record(db, AuditAction.SIGNED_OUT, actor=user, target_type="user", target_id=user.id)
    db.commit()


# Passwords


def request_password_reset(db: Session, *, email: str) -> None:
    """Queue a reset link; the worker sends it only to an active account."""
    user = _find_user(db, email)
    db.commit()
    _queue_request(AccountEmail.RESET_PASSWORD, user)


def reset_password(db: Session, *, token: str, new_password: str) -> None:
    """Set a new password from a reset link and end every existing session.

    The link proves the user reads this inbox, so an unverified email becomes verified.
    """
    used = user_tokens.consume(db, token, UserTokenPurpose.RESET_PASSWORD)
    if used is None:
        raise AppError("invalid_token", "This link is not valid or has expired.", 400)
    user = used.user
    user.password_hash = hash_password(new_password)
    user.session_version += 1
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
    sign_in_throttle.clear(db, user.email)
    record(db, AuditAction.PASSWORD_RESET, actor=user, target_type="user", target_id=user.id)
    db.commit()


def change_password(db: Session, user: User, *, current_password: str, new_password: str) -> None:
    """Change the password of a signed-in user and end every existing session.

    The caller issues a fresh session cookie for the current browser.
    """
    if not user.password_hash:
        raise AppError(
            "password_not_set",
            "This account has no password. Use forgot password to set one.",
            400,
        )
    attempt = sign_in_throttle.begin_attempt(db, user.email)
    db.commit()
    if not attempt.allowed:
        raise _too_many_attempts()
    if not verify_password(user.password_hash, current_password).ok:
        newly_locked = sign_in_throttle.attempt_failed(db, user.email)
        db.commit()
        if newly_locked:
            raise _too_many_attempts()
        raise AppError("invalid_password", "The current password is not correct.", 400)
    user.password_hash = hash_password(new_password)
    user.session_version += 1
    user_tokens.void_outstanding(db, user, UserTokenPurpose.RESET_PASSWORD)
    sign_in_throttle.clear(db, user.email)
    record(db, AuditAction.PASSWORD_CHANGED, actor=user, target_type="user", target_id=user.id)
    db.commit()
