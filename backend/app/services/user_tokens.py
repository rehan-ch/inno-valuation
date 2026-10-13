"""Single-use email tokens for email verification and password reset.

Only the SHA-256 hash is stored. The raw token is derived from the row id and the secret key
(``user_token_value``), so the email task can rebuild the link from the id alone.

Issuing a token voids the user's other outstanding tokens of the same purpose, so only the
newest link works. Using a token marks it used and voids the rest. ``used_at`` therefore
means "no longer usable", whether clicked or replaced.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import hash_token, user_token_value
from app.models import User, UserToken
from app.models.enums import UserTokenPurpose

TOKEN_LIFETIMES: Final[dict[UserTokenPurpose, timedelta]] = {
    UserTokenPurpose.VERIFY_EMAIL: timedelta(hours=24),
    UserTokenPurpose.RESET_PASSWORD: timedelta(hours=1),
}

# At most one new email of each kind per user in this time, so nobody can flood an inbox
# through the resend and forgot-password forms.
EMAIL_COOLDOWN: Final = timedelta(minutes=1)


def issue(db: Session, user: User, purpose: UserTokenPurpose) -> UserToken | None:
    """A new token row, or None if one was issued within ``EMAIL_COOLDOWN``. Caller commits."""
    now = datetime.now(UTC)
    recent = db.scalar(
        select(UserToken.id)
        .where(
            UserToken.user_id == user.id,
            UserToken.purpose == purpose,
            UserToken.created_at > now - EMAIL_COOLDOWN,
        )
        .limit(1)
    )
    if recent is not None:
        return None
    _void_outstanding(db, user, purpose, now)
    token = UserToken(user_id=user.id, purpose=purpose, expires_at=now + TOKEN_LIFETIMES[purpose])
    # The id is set first because the stored hash is derived from it.
    token.id = uuid.uuid4()
    token.token_hash = hash_token(user_token_value(token.id))
    db.add(token)
    db.flush()
    return token


def is_usable(token: UserToken, now: datetime | None = None) -> bool:
    return token.used_at is None and token.expires_at > (now or datetime.now(UTC))


def consume(db: Session, raw: str, purpose: UserTokenPurpose) -> User | None:
    """Use a token once. Returns its active user, or None if the token cannot be used.

    The row is locked so two clicks at once cannot both succeed. Caller commits.
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
    token.used_at = now
    _void_outstanding(db, user, purpose, now)
    db.flush()
    return user


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
