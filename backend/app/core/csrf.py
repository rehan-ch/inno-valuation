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
from app.core.sessions import CSRF_HEADER, csrf_cookie_name
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
    # "null" (sandboxed frames, some redirects) never equals the frontend origin.
    if origin is not None:
        # The setting is stored without a trailing slash; browsers send none either, but a
        # hand-made header with one is still the same origin.
        if origin.rstrip("/") != get_settings().frontend_origin:
            raise csrf_failed()
        return
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise csrf_failed()


def csrf_valid(request: Request, claims: SessionClaims) -> bool:
    """True for safe methods, or when header, cookie and session token all match."""
    if request.method not in UNSAFE_METHODS:
        return True
    header = request.headers.get(CSRF_HEADER)
    cookie = request.cookies.get(csrf_cookie_name())
    return bool(
        header
        and cookie
        and constant_time_equal(header, cookie)
        and constant_time_equal(header, claims.csrf)
    )


def enforce_csrf(request: Request, claims: SessionClaims) -> None:
    if not csrf_valid(request, claims):
        raise csrf_failed()
