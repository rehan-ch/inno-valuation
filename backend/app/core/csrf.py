"""Cross-site request protection.

Two layers:
1. ``require_trusted_origin`` runs on every API route. An unsafe request (POST, PUT,
   PATCH, DELETE) from a browser must come from the frontend origin. This also covers the
   routes that have no session yet (sign up, sign in, verify, forgot and reset password),
   so another site cannot sign a visitor in or out behind their back.
2. ``enforce_csrf`` runs inside the session dependencies. An unsafe request with a session
   must send ``X-CSRF-Token`` equal to the ``csrf_token`` cookie and to the token inside the
   signed session (signed double submit).
"""

from typing import Final

from fastapi import Request

from app.core.errors import AppError
from app.core.security import SessionClaims, constant_time_equal
from app.core.sessions import CSRF_COOKIE, CSRF_HEADER
from app.core.settings import get_settings

UNSAFE_METHODS: Final = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def csrf_failed() -> AppError:
    return AppError(
        "csrf_failed",
        "This request could not be checked. Reload the page and try again.",
        status_code=403,
    )


def require_trusted_origin(request: Request) -> None:
    """Reject unsafe browser requests from any origin other than the frontend.

    Clients that send no ``Origin`` and no ``Sec-Fetch-Site`` header (scripts, tests) are
    not browsers acting for a visitor, so they pass this layer; the CSRF token still applies
    to them when they use a session.
    """
    if request.method not in UNSAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin is not None:
        if origin.rstrip("/") != get_settings().frontend_origin.rstrip("/"):
            raise csrf_failed()
        return
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise csrf_failed()


def enforce_csrf(request: Request, claims: SessionClaims) -> None:
    if request.method not in UNSAFE_METHODS:
        return
    header = request.headers.get(CSRF_HEADER)
    cookie = request.cookies.get(CSRF_COOKIE)
    if (
        not header
        or not cookie
        or not constant_time_equal(header, cookie)
        or not constant_time_equal(header, claims.csrf)
    ):
        raise csrf_failed()
