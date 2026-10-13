"""Email and password sign-in: sign up, verify, sign in and out, lockout, reset, change."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import SessionClaims, encode_session, verify_password
from app.core.sessions import CSRF_COOKIE, SESSION_COOKIE
from app.core.settings import get_settings
from app.emails.backends import MemoryEmailBackend
from app.emails.messages import SUBJECTS, AccountEmail
from app.models import AuditEvent, SignInThrottle, User, UserToken
from app.models.enums import MembershipRole, UserTokenPurpose
from app.services import sign_in_throttle
from app.services.audit import AuditAction
from tests.api.helpers import (
    csrf,
    member,
    session_cookies,
    sign_in,
    signed_in,
    token_from,
    use_cookies,
)
from tests.factories import TEST_PASSWORD, UserFactory, UserTokenFactory, verified_user

SIGN_UP = "/api/v1/auth/sign-up"
VERIFY = "/api/v1/auth/verify-email"
RESEND = "/api/v1/auth/verify-email/resend"
SIGN_OUT = "/api/v1/auth/sign-out"
FORGOT = "/api/v1/auth/password/forgot"
RESET = "/api/v1/auth/password/reset"
ME = "/api/v1/me"
CHANGE_PASSWORD = "/api/v1/me/password"

NEW_PASSWORD = "a brand new password"


def _sign_up_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "email": "new.person@example.com",
        "name": "New Person",
        "password": TEST_PASSWORD,
        "accepted_terms": True,
    }
    body.update(overrides)
    return body


def _events(db: Session, action: AuditAction) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.action == action.value)))


def _user(db: Session, email: str) -> User:
    return db.scalars(select(User).where(User.email == email)).one()


def _set_cookie_headers(response: Any) -> dict[str, str]:
    headers = response.headers.get_list("set-cookie")
    return {header.split("=", 1)[0]: header.lower() for header in headers}


# Sign up


def test_sign_up_creates_unverified_user_and_emails_link(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    response = client.post(SIGN_UP, json=_sign_up_body(email="  New.Person@Example.com "))
    assert response.status_code == 202
    assert set(response.json()) == {"message"}

    user = _user(db, "new.person@example.com")
    assert user.email_verified_at is None
    assert user.terms_version == get_settings().terms_version
    assert user.terms_accepted_at is not None
    assert user.password_hash is not None
    assert verify_password(user.password_hash, TEST_PASSWORD).ok

    [message] = outbox.outbox
    assert message.to == "new.person@example.com"
    assert message.subject == SUBJECTS[AccountEmail.VERIFY_EMAIL]
    assert message.link.startswith(f"{get_settings().frontend_origin}/verify-email#token=")
    token = token_from(message)
    assert token in message.text
    assert token in message.html
    assert token not in message.subject

    [stored] = db.scalars(select(UserToken).where(UserToken.user_id == user.id))
    assert stored.purpose is UserTokenPurpose.VERIFY_EMAIL
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert stored.expires_at - datetime.now(UTC) > timedelta(hours=23)
    assert len(_events(db, AuditAction.SIGNED_UP)) == 1


def test_sign_up_does_not_put_the_raw_token_in_the_task(
    client: TestClient, db: Session, outbox: MemoryEmailBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.jobs.tasks.emails import send_account_email  # noqa: PLC0415

    calls: list[tuple[Any, ...]] = []
    original = send_account_email.delay

    def spy(*args: Any) -> Any:
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(send_account_email, "delay", spy)
    client.post(SIGN_UP, json=_sign_up_body())
    [message] = outbox.outbox
    [args] = calls
    assert token_from(message) not in repr(args)
    user = _user(db, "new.person@example.com")
    token_row = db.scalars(select(UserToken).where(UserToken.user_id == user.id)).one()
    assert args == ("verify_email", str(user.id), str(token_row.id))


@pytest.mark.parametrize(
    "overrides",
    [
        {"accepted_terms": False},
        {"accepted_terms": None},
        {"password": "x" * 9},
        {"password": "x" * 129},
        {"email": "not-an-email"},
        {"name": "   "},
        {"extra": "field"},
    ],
)
def test_sign_up_rejects_bad_input(
    client: TestClient, outbox: MemoryEmailBackend, overrides: dict[str, Any]
) -> None:
    response = client.post(SIGN_UP, json=_sign_up_body(**overrides))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert outbox.outbox == []


def test_sign_up_requires_terms_field(client: TestClient) -> None:
    body = _sign_up_body()
    del body["accepted_terms"]
    assert client.post(SIGN_UP, json=body).status_code == 422


@pytest.mark.parametrize("length", [10, 128])
def test_sign_up_password_length_bounds_accepted(client: TestClient, length: int) -> None:
    assert client.post(SIGN_UP, json=_sign_up_body(password="p" * length)).status_code == 202


def test_sign_up_with_registered_email_looks_the_same_and_changes_nothing(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    existing = verified_user(email="taken@example.com", name="Original")
    original_hash = existing.password_hash
    fresh = client.post(SIGN_UP, json=_sign_up_body(email="fresh@example.com"))
    taken = client.post(
        SIGN_UP, json=_sign_up_body(email="TAKEN@example.com", name="Intruder", password="x" * 12)
    )
    assert (taken.status_code, taken.json()) == (fresh.status_code, fresh.json())

    db.refresh(existing)
    assert existing.name == "Original"
    assert existing.password_hash == original_hash
    notices = [m for m in outbox.outbox if m.to == "taken@example.com"]
    assert [m.subject for m in notices] == [SUBJECTS[AccountEmail.ALREADY_REGISTERED]]
    assert notices[0].link.endswith("/sign-in")

    # A second try within the hour records the attempt but sends no second notice.
    client.post(SIGN_UP, json=_sign_up_body(email="taken@example.com"))
    assert len([m for m in outbox.outbox if m.to == "taken@example.com"]) == 1
    assert len(_events(db, AuditAction.SIGN_UP_EXISTING_EMAIL)) == 2


def test_sign_up_with_unverified_email_sends_a_new_link(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    UserFactory.create(email="pending@example.com")
    response = client.post(SIGN_UP, json=_sign_up_body(email="pending@example.com"))
    assert response.status_code == 202
    [message] = outbox.outbox
    assert message.subject == SUBJECTS[AccountEmail.VERIFY_EMAIL]


# Email verification


def test_verify_email_then_sign_in(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    client.post(SIGN_UP, json=_sign_up_body())
    token = token_from(outbox.outbox[0])

    blocked = sign_in(client, "new.person@example.com")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "email_not_verified"

    assert client.post(VERIFY, json={"token": token}).status_code == 200
    assert _user(db, "new.person@example.com").email_verified_at is not None
    assert len(_events(db, AuditAction.EMAIL_VERIFIED)) == 1

    reused = client.post(VERIFY, json={"token": token})
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "invalid_token"

    assert sign_in(client, "new.person@example.com").status_code == 200


def test_unverified_user_with_wrong_password_gets_the_generic_error(client: TestClient) -> None:
    UserFactory.create(email="pending@example.com")
    response = sign_in(client, "pending@example.com", "wrong password")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_expired_verification_token_is_rejected(client: TestClient, db: Session) -> None:
    from app.core.security import hash_token, user_token_value  # noqa: PLC0415

    token = UserTokenFactory.create(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    token.token_hash = hash_token(user_token_value(token.id))
    db.flush()
    response = client.post(VERIFY, json={"token": user_token_value(token.id)})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_token"


def test_garbage_token_is_rejected(client: TestClient) -> None:
    response = client.post(VERIFY, json={"token": "not-a-token"})
    assert response.json()["error"]["code"] == "invalid_token"


def test_resend_verification_does_not_reveal_accounts(
    client: TestClient, outbox: MemoryEmailBackend
) -> None:
    UserFactory.create(email="pending@example.com")
    verified_user(email="done@example.com")
    responses = [
        client.post(RESEND, json={"email": email})
        for email in ("nobody@example.com", "done@example.com", "pending@example.com")
    ]
    assert {(r.status_code, r.text) for r in responses} == {(202, responses[0].text)}
    assert [m.to for m in outbox.outbox] == ["pending@example.com"]

    # A second request inside the cooldown sends nothing more.
    client.post(RESEND, json={"email": "pending@example.com"})
    assert len(outbox.outbox) == 1


def test_resend_voids_the_older_link(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    client.post(SIGN_UP, json=_sign_up_body())
    first = token_from(outbox.outbox[0])
    # Move the first token out of the cooldown window.
    for row in db.scalars(select(UserToken)):
        row.created_at = datetime.now(UTC) - timedelta(minutes=5)
    db.flush()
    client.post(RESEND, json={"email": "new.person@example.com"})
    second = token_from(outbox.outbox[1])
    assert client.post(VERIFY, json={"token": first}).status_code == 400
    assert client.post(VERIFY, json={"token": second}).status_code == 200


# Sign in


def test_sign_in_sets_session_cookies_and_returns_me(client: TestClient, db: Session) -> None:
    user, org = member(MembershipRole.OWNER, email="owner@example.com")
    response = sign_in(client, "OWNER@example.com")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["email"] == "owner@example.com"
    assert body["email_verified"] is True
    assert body["active_organisation_id"] == str(org.id)
    assert body["memberships"] == [
        {
            "organisation_id": str(org.id),
            "organisation_name": org.name,
            "organisation_status": "active",
            "role": "owner",
        }
    ]

    cookies = _set_cookie_headers(response)
    session_header = cookies[SESSION_COOKIE]
    csrf_header = cookies[CSRF_COOKIE]
    for header in (session_header, csrf_header):
        assert "samesite=lax" in header
        assert "path=/" in header
        assert "max-age=604800" in header
        assert "secure" not in header  # test environment: plain http
    assert "httponly" in session_header
    assert "httponly" not in csrf_header

    db.refresh(user)
    assert user.last_login_at is not None
    assert len(_events(db, AuditAction.SIGNED_IN)) == 1
    assert client.get(ME).status_code == 200


def test_deployed_cookies_use_host_prefix_and_secure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    verified_user(email="person@example.com")
    monkeypatch.setattr(get_settings(), "environment", "production")
    cookies = _set_cookie_headers(sign_in(client, "person@example.com"))
    assert set(cookies) == {"__Host-iv_session", "__Host-csrf_token"}
    for header in cookies.values():
        assert "secure" in header
        assert "path=/" in header
        assert "domain=" not in header
    assert "httponly" in cookies["__Host-iv_session"]
    assert "httponly" not in cookies["__Host-csrf_token"]


def test_local_cookies_use_plain_names(client: TestClient) -> None:
    verified_user(email="person@example.com")
    cookies = _set_cookie_headers(sign_in(client, "person@example.com"))
    assert set(cookies) == {SESSION_COOKIE, CSRF_COOKIE}
    for header in cookies.values():
        assert "domain=" not in header


def test_deployed_session_is_read_from_the_host_cookie(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = verified_user()
    monkeypatch.setattr(get_settings(), "environment", "production")
    response = sign_in(client, user.email)
    # Read from the header: the test client's jar drops Secure cookies on plain http.
    token = _cookie_value(response, "__Host-iv_session")
    client.cookies.clear()
    # The plain name is ignored when deployed.
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get(ME).status_code == 401
    client.cookies.clear()
    client.cookies.set("__Host-iv_session", token)
    assert client.get(ME).status_code == 200


def _cookie_value(response: Any, name: str) -> str:
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return str(header.split("=", 1)[1].split(";", 1)[0])
    raise AssertionError(name)


def test_no_active_organisation_when_user_has_several(client: TestClient) -> None:
    user, _ = member(MembershipRole.MEMBER, email="two@example.com")
    member_of_second = member(MembershipRole.ADMIN)[1]
    from tests.factories import MembershipFactory  # noqa: PLC0415

    MembershipFactory.create(user=user, organisation=member_of_second, role=MembershipRole.ADMIN)
    body = sign_in(client, "two@example.com").json()
    assert body["active_organisation_id"] is None
    assert len(body["memberships"]) == 2


def test_wrong_password_and_unknown_email_look_the_same(client: TestClient, db: Session) -> None:
    verified_user(email="person@example.com")
    wrong = sign_in(client, "person@example.com", "wrong password")
    unknown = sign_in(client, "nobody@example.com", "wrong password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "invalid_credentials"
    assert SESSION_COOKIE not in client.cookies

    # Unknown emails leave no audit row; known accounts get one without the email.
    [event] = _events(db, AuditAction.SIGN_IN_FAILED)
    assert event.actor_user_id is not None
    assert event.details == {"reason": "invalid_credentials"}


@pytest.mark.parametrize("email", ["person@example.com", "nobody@example.com"])
def test_repeated_failures_lock_every_email_alike(
    client: TestClient, db: Session, email: str
) -> None:
    verified_user(email="person@example.com")
    codes = [
        sign_in(client, email, "wrong password").json()["error"]["code"]
        for _ in range(sign_in_throttle.MAX_ATTEMPTS)
    ]
    assert codes == ["invalid_credentials"] * (sign_in_throttle.MAX_ATTEMPTS - 1) + [
        "too_many_attempts"
    ]
    # Locked: even the right password is refused, and the response says nothing more.
    locked = sign_in(client, email)
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "too_many_attempts"
    # The throttle stores no email.
    assert all(email not in row.key_hash for row in db.scalars(select(SignInThrottle)))
    # Audit: one row per wrong password for a real account, one "locked" row per lock, and
    # nothing at all for an unknown email.
    sign_in(client, email)
    reasons = [event.details["reason"] for event in _events(db, AuditAction.SIGN_IN_FAILED)]
    if email == "person@example.com":
        assert reasons.count("invalid_credentials") == sign_in_throttle.MAX_ATTEMPTS - 1
        assert reasons.count("locked") == 1
    else:
        assert reasons == []


def test_sign_in_works_again_after_the_lock_ends(client: TestClient, db: Session) -> None:
    verified_user(email="person@example.com")
    for _ in range(sign_in_throttle.MAX_ATTEMPTS):
        sign_in(client, "person@example.com", "wrong password")
    row = db.scalars(select(SignInThrottle)).one()
    row.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert sign_in(client, "person@example.com").status_code == 200
    assert db.scalars(select(SignInThrottle)).all() == []


def test_disabled_user_cannot_sign_in(client: TestClient) -> None:
    verified_user(email="gone@example.com", is_active=False)
    right = sign_in(client, "gone@example.com")
    assert right.status_code == 403
    assert right.json()["error"]["code"] == "account_disabled"
    wrong = sign_in(client, "gone@example.com", "wrong password")
    assert wrong.json()["error"]["code"] == "invalid_credentials"


def test_google_only_user_cannot_use_a_password(client: TestClient) -> None:
    verified_user(email="google@example.com", password_hash=None, google_sub="google-123")
    response = sign_in(client, "google@example.com", "anything at all")
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_old_hash_parameters_are_upgraded_on_sign_in(client: TestClient, db: Session) -> None:
    weak = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(TEST_PASSWORD)
    user = verified_user(email="old@example.com", password_hash=weak)
    assert sign_in(client, "old@example.com").status_code == 200
    db.refresh(user)
    assert user.password_hash != weak
    assert user.password_hash is not None
    check = verify_password(user.password_hash, TEST_PASSWORD)
    assert check.ok
    assert not check.needs_rehash


# Sessions


def test_me_requires_a_session(client: TestClient) -> None:
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "not_authenticated", "message": "Please sign in."}}


def test_tampered_or_expired_session_is_rejected(client: TestClient) -> None:
    user = verified_user()
    signed_in(client, user)
    good = client.cookies[SESSION_COOKIE]
    client.cookies.set(SESSION_COOKIE, good[:-2] + ("AA" if not good.endswith("AA") else "BB"))
    assert client.get(ME).status_code == 401

    expired = encode_session(
        SessionClaims(
            user_id=user.id,
            session_version=user.session_version,
            csrf="x",
            active_org_id=None,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    client.cookies.set(SESSION_COOKIE, expired)
    assert client.get(ME).status_code == 401


def test_disabled_user_loses_access_immediately(client: TestClient, db: Session) -> None:
    user = verified_user()
    signed_in(client, user)
    user.is_active = False
    db.flush()
    assert client.get(ME).json()["error"]["code"] == "not_authenticated"


def test_sign_out_clears_the_session(client: TestClient, db: Session) -> None:
    signed_in(client, verified_user())
    response = client.post(SIGN_OUT, headers=csrf(client))
    assert response.status_code == 200
    assert SESSION_COOKIE not in client.cookies
    assert CSRF_COOKIE not in client.cookies
    assert client.get(ME).status_code == 401
    assert len(_events(db, AuditAction.SIGNED_OUT)) == 1


def test_sign_out_without_csrf_clears_cookies_but_is_not_audited(
    client: TestClient, db: Session
) -> None:
    signed_in(client, verified_user())
    response = client.post(SIGN_OUT)
    assert response.status_code == 200
    assert SESSION_COOKIE not in client.cookies
    assert _events(db, AuditAction.SIGNED_OUT) == []


def test_sign_out_without_a_session_still_succeeds(client: TestClient) -> None:
    assert client.post(SIGN_OUT).status_code == 200


# Forgot and reset password


def test_forgot_password_does_not_reveal_accounts(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    verified_user(email="person@example.com")
    unknown = client.post(FORGOT, json={"email": "nobody@example.com"})
    known = client.post(FORGOT, json={"email": "Person@example.com"})
    assert (
        (unknown.status_code, unknown.json())
        == (known.status_code, known.json())
        == (
            202,
            known.json(),
        )
    )
    [message] = outbox.outbox
    assert message.to == "person@example.com"
    assert message.subject == SUBJECTS[AccountEmail.RESET_PASSWORD]
    assert message.link.startswith(f"{get_settings().frontend_origin}/reset-password#token=")
    assert "1 hour" in message.text
    assert len(_events(db, AuditAction.PASSWORD_RESET_REQUESTED)) == 1


def test_reset_password_sets_the_password_and_ends_sessions(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    user = verified_user(email="person@example.com")
    signed_in(client, user)
    old_session = session_cookies(client)

    client.post(FORGOT, json={"email": "person@example.com"})
    token = token_from(outbox.outbox[0])
    client.cookies.clear()
    response = client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 200

    use_cookies(client, old_session)
    assert client.get(ME).status_code == 401
    client.cookies.clear()
    assert sign_in(client, "person@example.com").status_code == 401
    assert sign_in(client, "person@example.com", NEW_PASSWORD).status_code == 200
    again = client.post(RESET, json={"token": token, "new_password": "another new password"})
    assert again.json()["error"]["code"] == "invalid_token"
    assert len(_events(db, AuditAction.PASSWORD_RESET)) == 1


def test_reset_voids_other_reset_links(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    verified_user(email="person@example.com")
    client.post(FORGOT, json={"email": "person@example.com"})
    first = token_from(outbox.outbox[0])
    for row in db.scalars(select(UserToken)):
        row.created_at = datetime.now(UTC) - timedelta(minutes=5)
    db.flush()
    client.post(FORGOT, json={"email": "person@example.com"})
    second = token_from(outbox.outbox[1])

    assert (
        client.post(RESET, json={"token": first, "new_password": NEW_PASSWORD}).status_code == 400
    )
    assert (
        client.post(RESET, json={"token": second, "new_password": NEW_PASSWORD}).status_code == 200
    )
    usable = db.scalars(select(UserToken).where(UserToken.used_at.is_(None))).all()
    assert usable == []


def test_reset_verifies_the_email_and_clears_the_lock(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    user = UserFactory.create(email="pending@example.com")
    for _ in range(sign_in_throttle.MAX_ATTEMPTS):
        sign_in(client, "pending@example.com", "wrong password")
    client.post(FORGOT, json={"email": "pending@example.com"})
    token = token_from(outbox.outbox[0])
    client.post(RESET, json={"token": token, "new_password": NEW_PASSWORD})
    db.refresh(user)
    assert user.email_verified_at is not None
    assert sign_in(client, "pending@example.com", NEW_PASSWORD).status_code == 200


def test_reset_rejects_a_short_password(client: TestClient) -> None:
    response = client.post(RESET, json={"token": "whatever", "new_password": "short"})
    assert response.status_code == 422


# Change password


def test_change_password_ends_other_sessions_and_keeps_this_one(
    client: TestClient, db: Session
) -> None:
    user = verified_user(email="person@example.com")
    signed_in(client, user)
    other_device = session_cookies(client)
    signed_in(client, user)  # this browser

    response = client.post(
        CHANGE_PASSWORD,
        json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
        headers=csrf(client),
    )
    assert response.status_code == 200
    assert client.get(ME).status_code == 200  # re-issued cookie works
    this_device = session_cookies(client)

    use_cookies(client, other_device)
    assert client.get(ME).status_code == 401
    use_cookies(client, this_device)
    assert client.get(ME).status_code == 200
    assert len(_events(db, AuditAction.PASSWORD_CHANGED)) == 1
    client.cookies.clear()
    assert sign_in(client, "person@example.com", NEW_PASSWORD).status_code == 200


def test_change_password_needs_the_current_password(client: TestClient) -> None:
    signed_in(client, verified_user())
    response = client.post(
        CHANGE_PASSWORD,
        json={"current_password": "not my password", "new_password": NEW_PASSWORD},
        headers=csrf(client),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_password"


def test_change_password_needs_csrf(client: TestClient) -> None:
    signed_in(client, verified_user())
    response = client.post(
        CHANGE_PASSWORD, json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


# Pre-registration takeover

ATTACKER_PASSWORD = "attacker password 1"
VICTIM_PASSWORD = "victim password 22"
CHOSEN_PASSWORD = "chosen at verify 333"


def _sign_up_as(client: TestClient, password: str, name: str) -> None:
    body = _sign_up_body(email="victim@example.com", name=name, password=password)
    assert client.post(SIGN_UP, json=body).status_code == 202


def test_attacker_first_then_victim_must_choose_a_password(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    _sign_up_as(client, ATTACKER_PASSWORD, "Attacker")
    attacker_link = token_from(outbox.outbox[0])
    fresh = client.post(SIGN_UP, json=_sign_up_body(email="someone.else@example.com"))
    repeat = client.post(SIGN_UP, json=_sign_up_body(email="victim@example.com"))
    # The repeat sign-up looks exactly like a new one.
    assert (repeat.status_code, repeat.json()) == (fresh.status_code, fresh.json())
    victim_link = token_from(outbox.outbox[-1])
    user = _user(db, "victim@example.com")
    stored_hash = user.password_hash

    # The repeat sign-up changed nothing and voided the earlier link.
    assert user.password_hash == stored_hash
    assert client.post(VERIFY, json={"token": attacker_link}).status_code == 400

    missing = client.post(VERIFY, json={"token": victim_link})
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "password_required"
    chosen = client.post(VERIFY, json={"token": victim_link, "password": CHOSEN_PASSWORD})
    assert chosen.status_code == 200
    db.refresh(user)
    assert user.email_verified_at is not None
    assert user.session_version == 2
    assert sign_in(client, "victim@example.com", ATTACKER_PASSWORD).status_code == 401
    assert sign_in(client, "victim@example.com", CHOSEN_PASSWORD).status_code == 200


def test_victim_first_then_attacker_never_gets_the_attackers_password(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    _sign_up_as(client, VICTIM_PASSWORD, "Victim")
    victim_link = token_from(outbox.outbox[0])
    _sign_up_as(client, ATTACKER_PASSWORD, "Attacker")
    newest = token_from(outbox.outbox[1])
    user = _user(db, "victim@example.com")
    assert user.name == "Victim"
    assert verify_password(user.password_hash, VICTIM_PASSWORD).ok

    # The victim's one-click link was replaced; the newest one needs a password.
    assert client.post(VERIFY, json={"token": victim_link}).status_code == 400
    assert client.post(VERIFY, json={"token": newest}).json()["error"]["code"] == (
        "password_required"
    )
    assert (
        client.post(VERIFY, json={"token": newest, "password": CHOSEN_PASSWORD}).status_code == 200
    )
    assert sign_in(client, "victim@example.com", ATTACKER_PASSWORD).status_code == 401
    assert sign_in(client, "victim@example.com", CHOSEN_PASSWORD).status_code == 200


def test_password_required_without_a_password_keeps_the_link(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    _sign_up_as(client, ATTACKER_PASSWORD, "Attacker")
    _sign_up_as(client, VICTIM_PASSWORD, "Victim")
    link = token_from(outbox.outbox[-1])
    for _ in range(2):
        response = client.post(VERIFY, json={"token": link})
        assert response.json()["error"]["code"] == "password_required"
    row = db.scalars(select(UserToken).where(UserToken.used_at.is_(None))).one()
    assert row.requires_password
    assert _user(db, "victim@example.com").email_verified_at is None
    short = client.post(VERIFY, json={"token": link, "password": "short"})
    assert short.status_code == 422
    ok = client.post(VERIFY, json={"token": link, "password": CHOSEN_PASSWORD})
    assert ok.status_code == 200


def test_first_sign_up_verifies_in_one_click(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    client.post(SIGN_UP, json=_sign_up_body())
    link = token_from(outbox.outbox[0])
    # A password sent with a one-click link is ignored: the sign-up password stays.
    response = client.post(VERIFY, json={"token": link, "password": "ignored password"})
    assert response.status_code == 200
    assert sign_in(client, "new.person@example.com").status_code == 200


def test_a_resend_after_a_repeat_sign_up_still_requires_a_password(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    _sign_up_as(client, ATTACKER_PASSWORD, "Attacker")
    _sign_up_as(client, VICTIM_PASSWORD, "Victim")
    for row in db.scalars(select(UserToken)):
        row.created_at = datetime.now(UTC) - timedelta(minutes=5)
    db.flush()
    client.post(RESEND, json={"email": "victim@example.com"})
    resent = token_from(outbox.outbox[-1])
    assert client.post(VERIFY, json={"token": resent}).json()["error"]["code"] == (
        "password_required"
    )
    client.post(VERIFY, json={"token": resent, "password": CHOSEN_PASSWORD})
    assert sign_in(client, "victim@example.com", ATTACKER_PASSWORD).status_code == 401
    assert sign_in(client, "victim@example.com", CHOSEN_PASSWORD).status_code == 200


def test_verifying_ends_sessions_and_clears_the_lock(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    client.post(SIGN_UP, json=_sign_up_body())
    for _ in range(sign_in_throttle.MAX_ATTEMPTS):
        sign_in(client, "new.person@example.com", "wrong password")
    client.post(VERIFY, json={"token": token_from(outbox.outbox[0])})
    assert sign_in(client, "new.person@example.com").status_code == 200


# Resend and forgot password do the same work for every email


@pytest.mark.parametrize("path", [RESEND, FORGOT])
def test_requests_queue_one_task_for_every_email(
    client: TestClient, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.jobs.tasks.emails import request_account_email  # noqa: PLC0415

    user = UserFactory.create(email="known@example.com")
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(request_account_email, "delay", lambda *args: calls.append(args))
    client.post(path, json={"email": "nobody@example.com"})
    client.post(path, json={"email": "known@example.com"})
    kind = "verify_email" if path == RESEND else "reset_password"
    assert calls == [(kind, None), (kind, str(user.id))]
