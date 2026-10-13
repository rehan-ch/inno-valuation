"""Email and password accounts: sign up, verify email, sign in, reset and change password.

No function here reveals whether an email is registered: sign up, resend verification and
forgot password answer the same way for every email, and a failed sign-in gives one
generic error. Only someone who knows the right password learns that the email is not
verified yet or that the account is disabled.

Emails are queued after the commit, so the task always finds the rows it needs.
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
from app.jobs.tasks.emails import send_account_email
from app.models import AuditEvent, Membership, User
from app.models.enums import UserTokenPurpose
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


# Sign up and email verification


def sign_up(db: Session, *, email: str, name: str, password: str) -> None:
    """Create an account and email a verification link. Same outcome for a known email.

    For a known email nothing changes: an unverified account gets a fresh verification
    link, a verified one gets an "already registered" notice. The password is hashed in
    every case so the response time does not reveal which path ran.
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
        return
    if user.email_verified_at is None:
        token = user_tokens.issue(db, user, UserTokenPurpose.VERIFY_EMAIL)
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
    """Email a new verification link if the account exists and is not verified yet."""
    user = _find_user(db, email)
    if user is None or not user.is_active or user.email_verified_at is not None:
        return
    token = user_tokens.issue(db, user, UserTokenPurpose.VERIFY_EMAIL)
    db.commit()
    if token is not None:
        _queue_email(AccountEmail.VERIFY_EMAIL, user.id, token.id)


def verify_email(db: Session, *, token: str) -> None:
    user = user_tokens.consume(db, token, UserTokenPurpose.VERIFY_EMAIL)
    if user is None:
        raise AppError("invalid_token", "This link is not valid or has expired.", 400)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        record(db, AuditAction.EMAIL_VERIFIED, actor=user, target_type="user", target_id=user.id)
    db.commit()


# Sign in and sign out


def sign_in(db: Session, *, email: str, password: str) -> SignInResult:
    _require_password_sign_in()
    email = normalise_email(email)
    user = _find_user(db, email)

    if sign_in_throttle.is_locked(db, email):
        _record_failure(db, user, "locked")
        db.commit()
        raise _too_many_attempts()

    check = verify_password(user.password_hash if user else None, password)
    if user is None or not check.ok:
        locked = sign_in_throttle.record_failure(db, email)
        _record_failure(db, user, "invalid_credentials")
        db.commit()
        raise _too_many_attempts() if locked else _invalid_credentials()

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
    sign_in_throttle.clear(db, email)
    record(db, AuditAction.SIGNED_IN, actor=user, target_type="user", target_id=user.id)
    db.commit()
    return SignInResult(user=user, active_org_id=_default_org(db, user))


def _record_failure(db: Session, user: User | None, reason: str) -> None:
    # The email is stored only when it belongs to an account; unknown emails leave nothing.
    details: dict[str, str] = {"reason": reason}
    if user is not None:
        details["email"] = user.email
    record(
        db,
        AuditAction.SIGN_IN_FAILED,
        actor=user,
        target_type="user" if user else None,
        target_id=user.id if user else None,
        details=details,
    )


def _default_org(db: Session, user: User) -> uuid.UUID | None:
    """The organisation to start in: the only one, if the user belongs to exactly one."""
    org_ids = db.scalars(
        select(Membership.organisation_id).where(Membership.user_id == user.id).limit(2)
    ).all()
    return org_ids[0] if len(org_ids) == 1 else None


def record_sign_out(db: Session, user: User) -> None:
    record(db, AuditAction.SIGNED_OUT, actor=user, target_type="user", target_id=user.id)
    db.commit()


# Passwords


def request_password_reset(db: Session, *, email: str) -> None:
    """Email a reset link if an active account exists. Same outcome for every email."""
    user = _find_user(db, email)
    if user is None or not user.is_active:
        return
    token = user_tokens.issue(db, user, UserTokenPurpose.RESET_PASSWORD)
    if token is None:
        return
    record(
        db,
        AuditAction.PASSWORD_RESET_REQUESTED,
        actor=user,
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    _queue_email(AccountEmail.RESET_PASSWORD, user.id, token.id)


def reset_password(db: Session, *, token: str, new_password: str) -> None:
    """Set a new password from a reset link and end every existing session.

    The link proves the user reads this inbox, so an unverified email becomes verified.
    """
    user = user_tokens.consume(db, token, UserTokenPurpose.RESET_PASSWORD)
    if user is None:
        raise AppError("invalid_token", "This link is not valid or has expired.", 400)
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
    if sign_in_throttle.is_locked(db, user.email):
        raise _too_many_attempts()
    if not verify_password(user.password_hash, current_password).ok:
        locked = sign_in_throttle.record_failure(db, user.email)
        db.commit()
        if locked:
            raise _too_many_attempts()
        raise AppError("invalid_password", "The current password is not correct.", 400)
    user.password_hash = hash_password(new_password)
    user.session_version += 1
    user_tokens.void_outstanding(db, user, UserTokenPurpose.RESET_PASSWORD)
    sign_in_throttle.clear(db, user.email)
    record(db, AuditAction.PASSWORD_CHANGED, actor=user, target_type="user", target_id=user.id)
    db.commit()
