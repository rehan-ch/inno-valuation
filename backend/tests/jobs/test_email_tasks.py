"""The account email task, run eagerly (task_always_eager in tests)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import resend
from sqlalchemy.orm import Session

from app.core.security import user_token_value
from app.core.settings import get_settings
from app.emails.backends import (
    EmailNotConfiguredError,
    LogEmailBackend,
    MemoryEmailBackend,
    ResendEmailBackend,
    get_email_backend,
    override_email_backend,
)
from app.jobs.tasks.emails import SENT, SKIPPED, send_account_email
from app.models import UserToken
from app.models.enums import UserTokenPurpose
from app.services import user_tokens
from tests.factories import AuditEventFactory, UserFactory


def _verify_token(db: Session, **user_kwargs: Any) -> tuple[str, str]:
    user = UserFactory.create(**user_kwargs)
    token = user_tokens.issue(db, user, UserTokenPurpose.VERIFY_EMAIL)
    assert token is not None
    return str(user.id), str(token.id)


def test_sends_the_verification_link(db: Session, outbox: MemoryEmailBackend) -> None:
    user_id, token_id = _verify_token(db, email="person@example.com")
    assert send_account_email.delay("verify_email", user_id, token_id).get() == SENT
    [message] = outbox.outbox
    assert message.to == "person@example.com"
    assert user_token_value(uuid.UUID(token_id)) in message.link


def test_skips_a_used_or_expired_token(db: Session, outbox: MemoryEmailBackend) -> None:
    user_id, token_id = _verify_token(db)
    token = db.get(UserToken, uuid.UUID(token_id))
    assert token is not None
    token.used_at = datetime.now(UTC)
    db.flush()
    assert send_account_email.delay("verify_email", user_id, token_id).get() == SKIPPED
    token.used_at = None
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert send_account_email.delay("verify_email", user_id, token_id).get() == SKIPPED
    assert outbox.outbox == []


def test_skips_a_token_of_another_user_or_purpose(db: Session, outbox: MemoryEmailBackend) -> None:
    _, token_id = _verify_token(db)
    other = UserFactory.create()
    assert send_account_email.delay("verify_email", str(other.id), token_id).get() == SKIPPED
    owner_id, _ = _verify_token(db)
    assert send_account_email.delay("reset_password", owner_id, token_id).get() == SKIPPED
    assert outbox.outbox == []


def test_skips_a_disabled_user(db: Session, outbox: MemoryEmailBackend) -> None:
    user_id, token_id = _verify_token(db, is_active=False)
    assert send_account_email.delay("verify_email", user_id, token_id).get() == SKIPPED
    assert outbox.outbox == []


def test_sends_the_already_registered_notice(db: Session, outbox: MemoryEmailBackend) -> None:
    user = UserFactory.create()
    event = AuditEventFactory.create(actor_user_id=user.id)
    result = send_account_email.delay("already_registered", str(user.id), str(event.id)).get()
    assert result == SENT
    assert outbox.outbox[0].link.endswith("/sign-in")


def test_rejects_an_unknown_kind(db: Session) -> None:
    user = UserFactory.create()
    with pytest.raises(ValueError, match="not a valid"):
        send_account_email.delay("newsletter", str(user.id), str(user.id)).get()


# Backend selection


@pytest.fixture
def no_override() -> Any:
    override_email_backend(None)
    yield
    override_email_backend(None)


@pytest.mark.usefixtures("no_override")
def test_log_backend_in_development(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, db: Session
) -> None:
    monkeypatch.setattr(get_settings(), "resend_api_key", "")
    assert isinstance(get_email_backend(), LogEmailBackend)
    user_id, token_id = _verify_token(db, email="dev@example.com")
    with caplog.at_level(logging.INFO, logger="app.emails.backends"):
        send_account_email.delay("verify_email", user_id, token_id).get()
    [record] = [r for r in caplog.records if r.name == "app.emails.backends"]
    assert "dev@example.com" in record.getMessage()
    assert "/verify-email?token=" in record.getMessage()


@pytest.mark.usefixtures("no_override")
@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_without_key_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, db: Session, environment: str
) -> None:
    monkeypatch.setattr(get_settings(), "resend_api_key", "")
    monkeypatch.setattr(get_settings(), "environment", environment)
    with pytest.raises(EmailNotConfiguredError):
        get_email_backend()
    user_id, token_id = _verify_token(db)
    with pytest.raises(EmailNotConfiguredError):
        send_account_email.delay("verify_email", user_id, token_id).get()


@pytest.mark.usefixtures("no_override")
def test_log_backend_refuses_to_run_when_deployed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.emails.messages import render_already_registered  # noqa: PLC0415

    monkeypatch.setattr(get_settings(), "environment", "production")
    message = render_already_registered(to="a@example.com", origin="https://app.example.com")
    with pytest.raises(EmailNotConfiguredError):
        LogEmailBackend().send(message, idempotency_key="k")


@pytest.mark.usefixtures("no_override")
def test_resend_backend_when_key_is_set(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test_key")
    sent: list[tuple[Any, Any]] = []
    monkeypatch.setattr(
        resend.Emails, "send", lambda params, options=None: sent.append((params, options))
    )
    assert isinstance(get_email_backend(), ResendEmailBackend)

    user_id, token_id = _verify_token(db, email="real@example.com")
    send_account_email.delay("verify_email", user_id, token_id).get()
    [(params, options)] = sent
    assert params["to"] == ["real@example.com"]
    assert params["from"] == get_settings().email_from
    assert params["html"]
    assert params["text"]
    assert options == {"idempotency_key": f"verify_email:{token_id}"}
