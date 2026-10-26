from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.security import hash_token, user_token_value
from app.models.enums import UserTokenPurpose
from app.services import user_tokens
from tests.factories import UserFactory

VERIFY = UserTokenPurpose.VERIFY_EMAIL
RESET = UserTokenPurpose.RESET_PASSWORD


def _age(token: object, minutes: int) -> None:
    token.created_at = datetime.now(UTC) - timedelta(minutes=minutes)  # type: ignore[attr-defined]


def test_issue_stores_only_the_hash(db: Session) -> None:
    user = UserFactory.create()
    token = user_tokens.issue(db, user, VERIFY)
    assert token is not None
    raw = user_token_value(token.id)
    assert token.token_hash == hash_token(raw)
    assert raw not in token.token_hash
    assert token.expires_at - datetime.now(UTC) <= user_tokens.TOKEN_LIFETIMES[VERIFY]


def test_cooldown_blocks_a_second_token(db: Session) -> None:
    user = UserFactory.create()
    first = user_tokens.issue(db, user, VERIFY)
    assert user_tokens.issue(db, user, VERIFY) is None
    # Another purpose has its own cooldown.
    assert user_tokens.issue(db, user, RESET) is not None
    assert first is not None
    _age(first, 2)
    db.flush()
    assert user_tokens.issue(db, user, VERIFY) is not None


def test_new_verification_token_voids_the_old_one(db: Session) -> None:
    user = UserFactory.create()
    first = user_tokens.issue(db, user, VERIFY)
    assert first is not None
    _age(first, 2)
    second = user_tokens.issue(db, user, VERIFY)
    assert second is not None
    db.refresh(first)
    assert not user_tokens.is_usable(first)
    assert user_tokens.consume(db, user_token_value(first.id), VERIFY) is None
    used = user_tokens.consume(db, user_token_value(second.id), VERIFY)
    assert used is not None
    assert used.user == user


def test_new_reset_token_leaves_the_old_one_usable(db: Session) -> None:
    """Anyone can ask for a reset link, so a flood must not kill the owner's link. Using
    one link still voids the rest."""
    user = UserFactory.create()
    first = user_tokens.issue(db, user, RESET)
    assert first is not None
    _age(first, 2)
    second = user_tokens.issue(db, user, RESET)
    assert second is not None
    db.refresh(first)
    assert user_tokens.is_usable(first)
    assert user_tokens.is_usable(second)
    assert user_tokens.consume(db, user_token_value(first.id), RESET) is first
    db.refresh(second)
    assert not user_tokens.is_usable(second)


def test_consume_is_single_use_and_purpose_bound(db: Session) -> None:
    user = UserFactory.create()
    token = user_tokens.issue(db, user, VERIFY)
    assert token is not None
    raw = user_token_value(token.id)
    assert user_tokens.consume(db, raw, RESET) is None
    used = user_tokens.consume(db, raw, VERIFY)
    assert used is not None
    assert used.user == user
    assert user_tokens.consume(db, raw, VERIFY) is None


def test_consume_refuses_expired_tokens_and_disabled_users(db: Session) -> None:
    user = UserFactory.create()
    token = user_tokens.issue(db, user, VERIFY)
    assert token is not None
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert user_tokens.consume(db, user_token_value(token.id), VERIFY) is None

    disabled = UserFactory.create(is_active=False)
    other = user_tokens.issue(db, disabled, VERIFY)
    assert other is not None
    assert user_tokens.consume(db, user_token_value(other.id), VERIFY) is None


def test_sign_up_limit_skips_the_minute_cooldown_but_caps_the_hour(db: Session) -> None:
    user = UserFactory.create()
    issued = [
        user_tokens.issue(db, user, VERIFY, requires_password=True, limit=user_tokens.SIGN_UP_LIMIT)
        for _ in range(user_tokens.SIGN_UP_LIMIT.count + 1)
    ]
    assert all(token is not None for token in issued[:-1])
    assert issued[-1] is None


def test_a_contested_account_stays_contested(db: Session) -> None:
    user = UserFactory.create()
    plain = user_tokens.issue(db, user, VERIFY)
    assert plain is not None
    assert not plain.requires_password
    assert not user_tokens.is_contested(db, user)
    contested = user_tokens.issue(
        db, user, VERIFY, requires_password=True, limit=user_tokens.SIGN_UP_LIMIT
    )
    assert contested is not None
    # Even after the contested link expires, the next link still requires a password.
    contested.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    _age(contested, 2)
    _age(plain, 2)
    db.flush()
    resent = user_tokens.issue(db, user, VERIFY)
    assert resent is not None
    assert resent.requires_password


def test_only_verification_tokens_can_require_a_password(db: Session) -> None:
    user = UserFactory.create()
    with pytest.raises(ValueError, match="Only verification"):
        user_tokens.issue(db, user, RESET, requires_password=True)


def test_find_usable_does_not_use_the_token(db: Session) -> None:
    user = UserFactory.create()
    token = user_tokens.issue(db, user, VERIFY)
    assert token is not None
    raw = user_token_value(token.id)
    assert user_tokens.find_usable(db, raw, VERIFY) is token
    assert token.used_at is None
    assert user_tokens.consume(db, raw, VERIFY) is token
    assert user_tokens.find_usable(db, raw, VERIFY) is None
