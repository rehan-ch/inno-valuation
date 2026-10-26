"""Password hashing, token derivation and session JWTs. No database."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import PasswordHasher

from app.core import security
from app.core.security import (
    SESSION_AUDIENCE,
    SessionClaims,
    decode_session,
    encode_session,
    hash_password,
    hash_token,
    invitation_token_value,
    throttle_key,
    user_token_value,
    verify_password,
)
from app.core.settings import get_settings


def _claims(**overrides: object) -> SessionClaims:
    values: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "session_version": 3,
        "csrf": "csrf-value",
        "active_org_id": uuid.uuid4(),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "sid": "session-id",
    }
    values.update(overrides)
    return SessionClaims(**values)  # type: ignore[arg-type]


def test_password_round_trip() -> None:
    hashed = hash_password("a long password")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "a long password") == security.PasswordCheck(ok=True)
    assert not verify_password(hashed, "a long passwore").ok


@pytest.mark.parametrize("stored", [None, "", "$argon2id$not-a-real-hash", "plain text"])
def test_missing_or_malformed_hash_never_matches(stored: str | None) -> None:
    assert verify_password(stored, "anything").ok is False


def test_old_parameters_need_a_rehash() -> None:
    weak = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash("a long password")
    check = verify_password(weak, "a long password")
    assert check.ok
    assert check.needs_rehash


def test_user_token_is_derived_from_id_and_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    token_id = uuid.uuid4()
    value = user_token_value(token_id)
    assert value == user_token_value(token_id)
    assert value != user_token_value(uuid.uuid4())
    assert len(value) == 43  # 32 bytes, base64url without padding
    monkeypatch.setattr(get_settings(), "secret_key", "another secret key of enough length")
    assert user_token_value(token_id) != value


def test_invitation_token_uses_its_own_key() -> None:
    row_id = uuid.uuid4()
    value = invitation_token_value(row_id)
    assert value == invitation_token_value(row_id)
    assert len(value) == 43
    # The same row id never gives the same token for a user token and an invitation.
    assert value != user_token_value(row_id)


def test_hash_token_is_sha256_hex() -> None:
    assert len(hash_token("abc")) == 64
    assert hash_token("abc") != "abc"


def test_throttle_key_hides_the_email() -> None:
    key = throttle_key("person@example.com")
    assert len(key) == 64
    assert "person" not in key
    assert key == throttle_key("person@example.com")


def test_session_round_trip() -> None:
    claims = _claims()
    decoded = decode_session(encode_session(claims))
    assert decoded is not None
    assert decoded.user_id == claims.user_id
    assert decoded.session_version == 3
    assert decoded.csrf == "csrf-value"
    assert decoded.active_org_id == claims.active_org_id
    assert decoded.expires_at == claims.expires_at.replace(microsecond=0)
    assert decoded.sid == "session-id"


def test_session_ids_are_random() -> None:
    first, second = security.new_session_id(), security.new_session_id()
    assert first != second
    assert len(first) >= 20


@pytest.mark.parametrize("sid", [None, "", 7])
def test_session_without_a_usable_id_is_rejected(sid: object) -> None:
    payload = {
        "sub": str(uuid.uuid4()),
        "sv": 1,
        "csrf": "x",
        "aud": SESSION_AUDIENCE,
        "iat": 0,
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    }
    if sid is not None:
        payload["sid"] = sid
    token = jwt.encode(payload, security._subkey("session-jwt:v1"), algorithm="HS256")
    assert decode_session(token) is None


def test_address_throttle_key_is_separate_from_the_email_key() -> None:
    key = security.address_throttle_key("203.0.113.9")
    assert len(key) == 64
    assert "203.0.113.9" not in key
    assert key != throttle_key("203.0.113.9")


def test_session_without_active_organisation() -> None:
    decoded = decode_session(encode_session(_claims(active_org_id=None)))
    assert decoded is not None
    assert decoded.active_org_id is None


def test_expired_session_is_rejected() -> None:
    token = encode_session(_claims(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert decode_session(token) is None


# Forged with the raw SECRET_KEY on purpose (sessions use a derived key); locally it is short.
@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
def test_session_signed_with_another_key_is_rejected() -> None:
    payload = {
        "sub": str(uuid.uuid4()),
        "sv": 1,
        "csrf": "x",
        "aud": SESSION_AUDIENCE,
        "iat": 0,
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    }
    forged = jwt.encode(payload, get_settings().secret_key, algorithm="HS256")
    assert decode_session(forged) is None


def test_unsigned_session_is_rejected() -> None:
    token = encode_session(_claims())
    header, payload, _ = token.split(".")
    none_header = jwt.utils.base64url_encode(b'{"alg":"none","typ":"JWT"}').decode()
    assert decode_session(f"{none_header}.{payload}.") is None
    assert decode_session(f"{header}.{payload}.") is None


@pytest.mark.parametrize("bad", ["", "abc", "a.b.c"])
def test_garbage_session_is_rejected(bad: str) -> None:
    assert decode_session(bad) is None


def test_boolean_session_version_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "sub": str(uuid.uuid4()),
        "sv": True,
        "csrf": "x",
        "aud": SESSION_AUDIENCE,
        "iat": 0,
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, security._subkey("session-jwt:v1"), algorithm="HS256")
    assert decode_session(token) is None
