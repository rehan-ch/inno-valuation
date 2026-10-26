"""Single-use email tokens for email verification and password reset.

Only the SHA-256 hash is stored. The raw token is derived from the row id and the secret key
(``user_token_value``), so the email task can rebuild the link from the id alone.

Issuing a verification token voids the user's other outstanding verification tokens, so
only the newest link works. A new reset link leaves earlier ones alive until they expire or
one is used: forgot password can be asked for by anyone who knows the email, so a flood of
requests must not kill the link the owner is holding. Using a token of either purpose marks
it used and voids the rest. ``used_at`` therefore means "no longer usable", whether clicked
or replaced.

A verification token from a contested sign-up has ``requires_password`` set; using it
needs a new password (see ``app.services.auth``). Once an account has had such a token,
every later verification token for it requires a password too, until it is verified.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_token, user_token_value
from app.models import User, UserToken
from app.models.enums import UserTokenPurpose

TOKEN_LIFETIMES: Final[dict[UserTokenPurpose, timedelta]] = {
    UserTokenPurpose.VERIFY_EMAIL: timedelta(hours=24),
    UserTokenPurpose.RESET_PASSWORD: timedelta(hours=1),
}


@dataclass(frozen=True)
class RateLimit:
    """At most ``count`` new tokens of one purpose per user within ``period``."""

    count: int
    period: timedelta


# Resend and forgot password: at most one email per minute, so nobody can flood an inbox.
EMAIL_COOLDOWN: Final = RateLimit(count=1, period=timedelta(minutes=1))
# A repeat sign-up for an unverified email always gets its own link (the previous one is
# voided), so it skips the one-minute cooldown but is capped per hour.
SIGN_UP_LIMIT: Final = RateLimit(count=5, period=timedelta(hours=1))


def issue(
    db: Session,
    user: User,
    purpose: UserTokenPurpose,
    *,
    requires_password: bool = False,
    limit: RateLimit = EMAIL_COOLDOWN,
) -> UserToken | None:
    """A new token row, or None when ``limit`` is reached. Caller commits.

    A verification token requires a password when asked to, or when any earlier
    verification token of this user did (a contested account stays contested).
    """
    if requires_password and purpose is not UserTokenPurpose.VERIFY_EMAIL:
        raise ValueError("Only verification tokens can require a password.")
    now = datetime.now(UTC)
    recent = db.scalar(
        select(func.count())
        .select_from(UserToken)
        .where(
            UserToken.user_id == user.id,
            UserToken.purpose == purpose,
            UserToken.created_at > now - limit.period,
        )
    )
    if (recent or 0) >= limit.count:
        return None
    if purpose is UserTokenPurpose.VERIFY_EMAIL:
        if not requires_password:
            requires_password = is_contested(db, user)
        _void_outstanding(db, user, purpose, now)
    token = UserToken(
        user_id=user.id,
        purpose=purpose,
        expires_at=now + TOKEN_LIFETIMES[purpose],
        requires_password=requires_password,
    )
    # The id is set first because the stored hash is derived from it.
    token.id = uuid.uuid4()
    token.token_hash = hash_token(user_token_value(token.id))
    db.add(token)
    db.flush()
    return token


def is_contested(db: Session, user: User) -> bool:
    """True if any verification token of the user ever required a password."""
    found = db.scalar(
        select(UserToken.id)
        .where(
            UserToken.user_id == user.id,
            UserToken.purpose == UserTokenPurpose.VERIFY_EMAIL,
            UserToken.requires_password.is_(True),
        )
        .limit(1)
    )
    return found is not None


def is_usable(token: UserToken, now: datetime | None = None) -> bool:
    return token.used_at is None and token.expires_at > (now or datetime.now(UTC))


def find_usable(db: Session, raw: str, purpose: UserTokenPurpose) -> UserToken | None:
    """The usable token for ``raw`` (its user is active), locked for update, or None.

    Does not use it: call ``mark_used``. The lock means two clicks at once cannot both
    succeed.
    """
    now = datetime.now(UTC)
    token = db.scalar(
        select(UserToken)
        .where(UserToken.token_hash == hash_token(raw), UserToken.purpose == purpose)
        .with_for_update()
    )
    if token is None or not is_usable(token, now):
        return None
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        return None
    return token


def mark_used(db: Session, token: UserToken) -> None:
    """Use the token and void the user's other outstanding tokens of its purpose."""
    now = datetime.now(UTC)
    token.used_at = now
    _void_outstanding(db, token.user, token.purpose, now)
    db.flush()


def consume(db: Session, raw: str, purpose: UserTokenPurpose) -> UserToken | None:
    """Find and use a token once. Returns the used token, or None. Caller commits."""
    token = find_usable(db, raw, purpose)
    if token is not None:
        mark_used(db, token)
    return token


def void_outstanding(db: Session, user: User, purpose: UserTokenPurpose) -> None:
    _void_outstanding(db, user, purpose, datetime.now(UTC))


def _void_outstanding(db: Session, user: User, purpose: UserTokenPurpose, now: datetime) -> None:
    db.execute(
        update(UserToken)
        .where(
            UserToken.user_id == user.id,
            UserToken.purpose == purpose,
            UserToken.used_at.is_(None),
        )
        .values(used_at=now)
        .execution_options(synchronize_session="fetch")
    )
