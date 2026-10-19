"""The account email task, run eagerly (task_always_eager in tests)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import resend
from sqlalchemy.orm import Session

from app.core.security import invitation_token_value, user_token_value
from app.core.settings import get_settings
from app.emails.backends import (
    EmailNotConfiguredError,
    LogEmailBackend,
    MemoryEmailBackend,
    ResendEmailBackend,
    get_email_backend,
    override_email_backend,
)
from app.jobs.tasks.emails import (
    SENT,
    SKIPPED,
    request_account_email,
    send_account_email,
    send_organisation_email,
)
from app.models import UserToken
from app.models.enums import OrganisationStatus, UserTokenPurpose
from app.services import user_tokens
from app.services.audit import AuditAction
from tests.factories import (
    AuditEventFactory,
    ConsultantGrantFactory,
    InvitationFactory,
    OrganisationFactory,
    UserFactory,
)


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
    event = AuditEventFactory.create(
        actor_user_id=user.id, action=AuditAction.SIGN_UP_EXISTING_EMAIL.value
    )
    result = send_account_email.delay("already_registered", str(user.id), str(event.id)).get()
    assert result == SENT
    assert outbox.outbox[0].link.endswith("/sign-in")


def test_already_registered_checks_its_audit_event(db: Session, outbox: MemoryEmailBackend) -> None:
    user = UserFactory.create()
    other = UserFactory.create()
    wrong_action = AuditEventFactory.create(actor_user_id=user.id, action="user.signed_in")
    wrong_actor = AuditEventFactory.create(
        actor_user_id=other.id, action=AuditAction.SIGN_UP_EXISTING_EMAIL.value
    )
    for ref in (wrong_action.id, wrong_actor.id, uuid.uuid4()):
        result = send_account_email.delay("already_registered", str(user.id), str(ref)).get()
        assert result == SKIPPED
    assert outbox.outbox == []


def test_request_task_skips_unknown_emails(outbox: MemoryEmailBackend) -> None:
    assert request_account_email.delay("reset_password", None).get() == SKIPPED
    assert outbox.outbox == []


def test_request_task_issues_and_sends_a_reset_link(
    db: Session, outbox: MemoryEmailBackend
) -> None:
    user = UserFactory.create(email="reset@example.com")
    assert request_account_email.delay("reset_password", str(user.id)).get() == SENT
    [message] = outbox.outbox
    assert "/reset-password#token=" in message.link
    # A re-delivered task hits the rate limit and sends nothing more.
    assert request_account_email.delay("reset_password", str(user.id)).get() == SKIPPED
    assert len(outbox.outbox) == 1


def test_request_task_refuses_other_kinds(db: Session) -> None:
    user = UserFactory.create()
    with pytest.raises(ValueError, match="cannot be requested"):
        request_account_email.delay("already_registered", str(user.id)).get()


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
    assert "/verify-email#token=" in record.getMessage()


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


# Team emails


def test_sends_an_invitation(db: Session, outbox: MemoryEmailBackend) -> None:
    invitation = InvitationFactory.create(email="guest@example.com")
    result = send_organisation_email.delay("invitation", str(invitation.id)).get()
    assert result == SENT
    [message] = outbox.outbox
    assert message.to == "guest@example.com"
    assert invitation_token_value(invitation.id) in message.link


@pytest.mark.parametrize(
    "change",
    [
        {"revoked_at": datetime.now(UTC)},
        {"accepted_at": datetime.now(UTC)},
        {"expires_at": datetime.now(UTC) - timedelta(seconds=1)},
    ],
)
def test_skips_an_invitation_that_is_no_longer_pending(
    db: Session, outbox: MemoryEmailBackend, change: dict[str, Any]
) -> None:
    invitation = InvitationFactory.create(**change)
    assert send_organisation_email.delay("invitation", str(invitation.id)).get() == SKIPPED
    assert outbox.outbox == []


def test_skips_team_emails_for_an_archived_organisation(
    db: Session, outbox: MemoryEmailBackend
) -> None:
    org = OrganisationFactory.create(status=OrganisationStatus.ARCHIVED)
    invitation = InvitationFactory.create(organisation=org)
    grant = ConsultantGrantFactory.create(organisation=org)
    assert send_organisation_email.delay("invitation", str(invitation.id)).get() == SKIPPED
    assert send_organisation_email.delay("consultant_access", str(grant.id)).get() == SKIPPED
    assert outbox.outbox == []


def test_sends_consultant_access_only_while_waiting(
    db: Session, outbox: MemoryEmailBackend
) -> None:
    grant = ConsultantGrantFactory.create(consultant_email="amy@example.com")
    assert send_organisation_email.delay("consultant_access", str(grant.id)).get() == SENT
    assert outbox.outbox[0].to == "amy@example.com"
    grant.revoked_at = datetime.now(UTC)
    db.flush()
    assert send_organisation_email.delay("consultant_access", str(grant.id)).get() == SKIPPED


def test_skips_an_unknown_team_row(db: Session, outbox: MemoryEmailBackend) -> None:
    for kind in ("invitation", "consultant_access"):
        assert send_organisation_email.delay(kind, str(uuid.uuid4())).get() == SKIPPED
    assert outbox.outbox == []
