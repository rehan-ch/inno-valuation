"""Security primitives: argon2 password hashing, single-use tokens and session JWTs.

Every key used here is derived from ``SECRET_KEY`` with a fixed label, so the session JWT
key, the email-token key and the throttle key are independent of each other.
"""

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from typing import Any, Final

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.settings import get_settings

PASSWORD_MIN_LENGTH: Final = 8
PASSWORD_MAX_LENGTH: Final = 128

# argon2id with the library defaults (RFC 9106 low-memory profile). When the defaults
# change in a library upgrade, ``check_needs_rehash`` reports old hashes and sign-in
# re-hashes them.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


@cache
def _dummy_hash() -> str:
    # Verified against when there is no real hash, so a sign-in for an unknown email
    # takes as long as one for a known email.
    return _hasher.hash(secrets.token_urlsafe(16))


@dataclass(frozen=True)
class PasswordCheck:
    ok: bool
    needs_rehash: bool = False


def verify_password(password_hash: str | None, password: str) -> PasswordCheck:
    """Check a password against a stored hash. Always does the argon2 work.

    A missing hash (Google-only user, unknown email) or a malformed hash never matches.
    """
    if not password_hash:
        _verify_quietly(_dummy_hash(), password)
        return PasswordCheck(ok=False)
    if not _verify_quietly(password_hash, password):
        return PasswordCheck(ok=False)
    return PasswordCheck(ok=True, needs_rehash=_hasher.check_needs_rehash(password_hash))


def _verify_quietly(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Keys


def _subkey(label: str) -> bytes:
    secret = get_settings().secret_key.encode()
    return hmac.new(secret, f"innovaluation:{label}".encode(), hashlib.sha256).digest()


# Single-use email tokens (verify email, reset password)


def hash_token(raw: str) -> str:
    """SHA-256 hex digest, the only form in which tokens are stored."""
    return hashlib.sha256(raw.encode()).hexdigest()


def user_token_value(token_id: uuid.UUID) -> str:
    """The raw token for a ``user_tokens`` row, derived from its id and the secret key.

    Deriving it means the email task needs only the row id, so the raw token never sits
    in the Celery broker. A database leak alone does not reveal it (the key is needed).
    """
    digest = hmac.new(_subkey("user-token:v1"), token_id.bytes, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def invitation_token_value(invitation_id: uuid.UUID) -> str:
    """The raw token for an ``invitations`` row, derived like ``user_token_value`` under its
    own key, so a user token can never pass as an invitation token or the reverse."""
    digest = hmac.new(_subkey("invitation:v1"), invitation_id.bytes, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def throttle_key(normalised_email: str) -> str:
    """Keyed hash of an email for the sign-in throttle. No email is stored."""
    return hmac.new(
        _subkey("sign-in-throttle:v1"), normalised_email.encode(), hashlib.sha256
    ).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


# Session JWT

JWT_ALGORITHM: Final = "HS256"
SESSION_AUDIENCE: Final = "innovaluation:session"


@dataclass(frozen=True)
class SessionClaims:
    user_id: uuid.UUID
    session_version: int
    csrf: str
    active_org_id: uuid.UUID | None
    expires_at: datetime


def encode_session(claims: SessionClaims) -> str:
    payload: dict[str, Any] = {
        "sub": str(claims.user_id),
        "sv": claims.session_version,
        "csrf": claims.csrf,
        "org": str(claims.active_org_id) if claims.active_org_id else None,
        "aud": SESSION_AUDIENCE,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(claims.expires_at.timestamp()),
    }
    return jwt.encode(payload, _subkey("session-jwt:v1"), algorithm=JWT_ALGORITHM)


def decode_session(token: str) -> SessionClaims | None:
    """Verified claims, or None for any bad, expired or tampered token."""
    try:
        payload = jwt.decode(
            token,
            _subkey("session-jwt:v1"),
            algorithms=[JWT_ALGORITHM],
            audience=SESSION_AUDIENCE,
            options={"require": ["sub", "sv", "csrf", "aud", "iat", "exp"]},
        )
        org = payload.get("org")
        session_version = payload["sv"]
        csrf = payload["csrf"]
        if (
            type(session_version) is not int  # bool is an int subclass; reject it
            or not isinstance(csrf, str)
            or not csrf
        ):
            return None
        return SessionClaims(
            user_id=uuid.UUID(payload["sub"]),
            session_version=session_version,
            csrf=csrf,
            active_org_id=uuid.UUID(org) if org else None,
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
        return None
