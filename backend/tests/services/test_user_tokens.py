from datetime import UTC, datetime, timedelta

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


def test_new_token_voids_the_old_one(db: Session) -> None:
    user = UserFactory.create()
    first = user_tokens.issue(db, user, RESET)
    assert first is not None
    _age(first, 2)
    second = user_tokens.issue(db, user, RESET)
    assert second is not None
    db.refresh(first)
    assert not user_tokens.is_usable(first)
    assert user_tokens.consume(db, user_token_value(first.id), RESET) is None
    assert user_tokens.consume(db, user_token_value(second.id), RESET) == user


def test_consume_is_single_use_and_purpose_bound(db: Session) -> None:
    user = UserFactory.create()
    token = user_tokens.issue(db, user, VERIFY)
    assert token is not None
    raw = user_token_value(token.id)
    assert user_tokens.consume(db, raw, RESET) is None
    assert user_tokens.consume(db, raw, VERIFY) == user
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
