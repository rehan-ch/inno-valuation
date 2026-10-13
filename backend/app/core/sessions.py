"""Session cookies: issue, refresh, read and clear.

Two cookies:
- ``iv_session``: the signed session JWT. httpOnly, so page scripts cannot read it.
- ``csrf_token``: readable by the frontend, which echoes it in the ``X-CSRF-Token``
  header on every unsafe request. The same value is inside the JWT, so a cookie planted
  by another site cannot pass the check (signed double submit).

Both are ``SameSite=Lax``, ``Path=/``, and ``Secure`` in staging and production.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Final

from fastapi import Request, Response

from app.core.security import (
    SessionClaims,
    decode_session,
    encode_session,
    new_csrf_token,
)
from app.core.settings import get_settings
from app.models import User

SESSION_COOKIE: Final = "iv_session"
CSRF_COOKIE: Final = "csrf_token"
CSRF_HEADER: Final = "X-CSRF-Token"


def session_lifetime() -> timedelta:
    return timedelta(days=get_settings().session_lifetime_days)


def start_session(
    response: Response, user: User, *, active_org_id: uuid.UUID | None
) -> SessionClaims:
    """A new session with a fresh CSRF token and the full lifetime."""
    claims = SessionClaims(
        user_id=user.id,
        session_version=user.session_version,
        csrf=new_csrf_token(),
        active_org_id=active_org_id,
        expires_at=datetime.now(UTC) + session_lifetime(),
    )
    _set_cookies(response, claims)
    return claims


def refresh_session(
    response: Response, claims: SessionClaims, *, active_org_id: uuid.UUID | None
) -> SessionClaims:
    """Re-issue the same session with a new active organisation.

    Keeps the CSRF token (requests already in flight stay valid) and the original end
    time (switching organisation never extends a session).
    """
    updated = SessionClaims(
        user_id=claims.user_id,
        session_version=claims.session_version,
        csrf=claims.csrf,
        active_org_id=active_org_id,
        expires_at=claims.expires_at,
    )
    _set_cookies(response, updated)
    return updated


def read_session(request: Request) -> SessionClaims | None:
    token = request.cookies.get(SESSION_COOKIE)
    return decode_session(token) if token else None


def clear_session(response: Response) -> None:
    secure = get_settings().is_deployed
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, httponly=False, samesite="lax")


def _set_cookies(response: Response, claims: SessionClaims) -> None:
    secure = get_settings().is_deployed
    max_age = max(0, round((claims.expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        SESSION_COOKIE,
        encode_session(claims),
        max_age=max_age,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE,
        claims.csrf,
        max_age=max_age,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )
