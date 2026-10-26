"""Service-level checks of the auth flows (the request tests cover the HTTP side)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import SessionClaims, user_token_value
from app.emails.backends import MemoryEmailBackend
from app.models import AuditEvent, RevokedSession, User
from app.models.enums import MembershipRole, OrganisationStatus, UserTokenPurpose
from app.services import auth, user_tokens
from app.services.audit import AuditAction
from tests.factories import (
    TEST_PASSWORD,
    MembershipFactory,
    OrganisationFactory,
    UserFactory,
    verified_user,
)


def test_sign_up_then_verify(db: Session, outbox: MemoryEmailBackend) -> None:
    auth.sign_up(db, email=" Someone@Example.com", name="Someone", password=TEST_PASSWORD)
    user = db.scalars(select(User).where(User.email == "someone@example.com")).one()
    assert user.session_version == 1
    [message] = outbox.outbox
    token = message.link.split("#token=", 1)[1]
    auth.verify_email(db, token=token)
    assert user.email_verified_at is not None


def test_sign_in_picks_the_only_organisation(db: Session) -> None:
    user = verified_user()
    membership = MembershipFactory.create(user=user, role=MembershipRole.MEMBER)
    result = auth.sign_in(db, email=user.email, password=TEST_PASSWORD)
    assert result.user == user
    assert result.active_org_id == membership.organisation_id


def test_no_default_organisation_when_the_only_one_is_archived(db: Session) -> None:
    user = verified_user()
    archived = OrganisationFactory.create(status=OrganisationStatus.ARCHIVED)
    MembershipFactory.create(user=user, organisation=archived, role=MembershipRole.OWNER)
    assert auth._default_org(db, user) is None
    assert auth.sign_in(db, email=user.email, password=TEST_PASSWORD).active_org_id is None


def test_stale_contested_link_cannot_change_a_verified_users_password(db: Session) -> None:
    """A link that required a password, used after the email is verified another way, is
    spent but changes nothing: the password it carries is ignored."""
    user = verified_user()
    before = user.password_hash
    token = user_tokens.issue(
        db,
        user,
        UserTokenPurpose.VERIFY_EMAIL,
        requires_password=True,
        limit=user_tokens.SIGN_UP_LIMIT,
    )
    assert token is not None
    auth.verify_email(db, token=user_token_value(token.id), password="an attackers choice 9")
    db.refresh(user)
    assert user.password_hash == before
    assert user.session_version == 1
    assert token.used_at is not None


def test_failed_sign_in_audit(db: Session) -> None:
    user = verified_user(email="known@example.com")
    for email in ("nobody@example.com", "known@example.com"):
        with pytest.raises(AppError) as info:
            auth.sign_in(db, email=email, password="wrong password")
        assert info.value.code == "invalid_credentials"
    # Only the real account leaves a row, and it holds no email.
    [event] = db.scalars(
        select(AuditEvent).where(AuditEvent.action == AuditAction.SIGN_IN_FAILED.value)
    )
    assert event.actor_user_id == user.id
    assert event.details == {"reason": "invalid_credentials"}


def test_verify_email_bumps_the_session_version(db: Session, outbox: MemoryEmailBackend) -> None:
    auth.sign_up(db, email="new@example.com", name="New", password=TEST_PASSWORD)
    user = db.scalars(select(User).where(User.email == "new@example.com")).one()
    auth.verify_email(db, token=outbox.outbox[0].link.split("#token=", 1)[1])
    assert user.session_version == 2


def test_disabled_account_sign_up_changes_nothing(db: Session, outbox: MemoryEmailBackend) -> None:
    user = UserFactory.create(email="gone@example.com", is_active=False)
    auth.sign_up(db, email="gone@example.com", name="Someone", password="another password")
    assert outbox.outbox == []
    assert user.name != "Someone"


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


def test_signing_out_twice_with_one_session_revokes_it_once(db: Session) -> None:
    """A double click or two tabs: both calls pass, one revocation row results."""
    user = verified_user()
    claims = SessionClaims(
        user_id=user.id,
        session_version=user.session_version,
        csrf="csrf",
        active_org_id=None,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        sid="one-session",
    )
    auth.sign_out(db, user, claims)
    auth.sign_out(db, user, claims)
    rows = db.scalars(select(RevokedSession).where(RevokedSession.sid == "one-session")).all()
    assert len(rows) == 1
    assert auth.session_revoked(db, "one-session")
