"""Service-level checks of the auth flows (the request tests cover the HTTP side)."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.emails.backends import MemoryEmailBackend
from app.models import AuditEvent, User
from app.models.enums import MembershipRole
from app.services import auth
from app.services.audit import AuditAction
from tests.factories import (
    TEST_PASSWORD,
    MembershipFactory,
    UserFactory,
    verified_user,
)


def test_sign_up_then_verify(db: Session, outbox: MemoryEmailBackend) -> None:
    auth.sign_up(db, email=" Someone@Example.com", name="Someone", password=TEST_PASSWORD)
    user = db.scalars(select(User).where(User.email == "someone@example.com")).one()
    assert user.session_version == 1
    [message] = outbox.outbox
    token = message.link.split("token=", 1)[1]
    auth.verify_email(db, token=token)
    assert user.email_verified_at is not None


def test_sign_in_picks_the_only_organisation(db: Session) -> None:
    user = verified_user()
    membership = MembershipFactory.create(user=user, role=MembershipRole.MEMBER)
    result = auth.sign_in(db, email=user.email, password=TEST_PASSWORD)
    assert result.user == user
    assert result.active_org_id == membership.organisation_id


def test_failed_sign_in_is_audited_and_kept(db: Session) -> None:
    with pytest.raises(AppError) as info:
        auth.sign_in(db, email="nobody@example.com", password="wrong password")
    assert info.value.code == "invalid_credentials"
    [event] = db.scalars(
        select(AuditEvent).where(AuditEvent.action == AuditAction.SIGN_IN_FAILED.value)
    )
    assert event.actor_user_id is None
    assert event.details == {"reason": "invalid_credentials"}


def test_change_password_bumps_the_session_version(db: Session) -> None:
    user = verified_user()
    auth.change_password(db, user, current_password=TEST_PASSWORD, new_password="another password")
    assert user.session_version == 2


def test_change_password_for_a_google_only_user(db: Session) -> None:
    user = UserFactory.create(password_hash=None, google_sub="g-1")
    with pytest.raises(AppError) as info:
        auth.change_password(db, user, current_password="x", new_password="another password")
    assert info.value.code == "password_not_set"


def test_password_sign_in_switch_is_provisional() -> None:
    # Q14 is open: the switch exists so "Google only" stays a one-line change.
    assert auth.PASSWORD_SIGN_IN_ENABLED is True


def test_sign_in_refused_when_password_sign_in_is_off(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth, "PASSWORD_SIGN_IN_ENABLED", False)
    with pytest.raises(AppError) as info:
        auth.sign_in(db, email="a@example.com", password=TEST_PASSWORD)
    assert info.value.code == "password_sign_in_disabled"
