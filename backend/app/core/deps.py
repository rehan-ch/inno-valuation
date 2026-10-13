"""FastAPI dependencies shared by every router.

- ``current_session``: a valid session cookie for an active, verified user whose session
  version still matches; on unsafe methods also the CSRF check. 401 ``not_authenticated``.
- ``current_user``: the user of ``current_session``.
- ``current_org``: the active organisation from the session, re-checked against the
  membership (or a live consultant grant) on every request. 404 ``not_found`` when access
  is gone; 409 ``no_active_organisation`` when none is picked.
- ``require_role(*roles)`` and ``require_permission(permission)``: ``current_org`` plus a
  role check. 403 ``forbidden``.

The organisation always comes from ``current_org``, never from a path, query or body.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.csrf import enforce_csrf
from app.core.errors import AppError
from app.core.permissions import OrgContext, OrgRole, Permission
from app.core.security import SessionClaims
from app.core.sessions import read_session
from app.db.session import get_db
from app.models import User
from app.services.access import resolve_org_access

__all__ = [
    "AuthContext",
    "current_org",
    "current_session",
    "current_user",
    "get_db",
    "optional_session",
    "require_permission",
    "require_role",
]


@dataclass(frozen=True)
class AuthContext:
    user: User
    claims: SessionClaims


def _authenticate(request: Request, db: Session) -> AuthContext | None:
    claims = read_session(request)
    if claims is None:
        return None
    user = db.get(User, claims.user_id)
    if (
        user is None
        or not user.is_active
        or user.email_verified_at is None
        or user.session_version != claims.session_version
    ):
        return None
    return AuthContext(user=user, claims=claims)


def current_session(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    auth = _authenticate(request, db)
    if auth is None:
        raise AppError("not_authenticated", "Please sign in.", 401)
    enforce_csrf(request, auth.claims)
    return auth


def optional_session(request: Request, db: Session = Depends(get_db)) -> AuthContext | None:
    """The session if there is a valid one (CSRF still checked), else None."""
    auth = _authenticate(request, db)
    if auth is not None:
        enforce_csrf(request, auth.claims)
    return auth


def current_user(auth: AuthContext = Depends(current_session)) -> User:
    return auth.user


def current_org(
    auth: AuthContext = Depends(current_session), db: Session = Depends(get_db)
) -> OrgContext:
    org_id = auth.claims.active_org_id
    if org_id is None:
        raise AppError("no_active_organisation", "Choose an organisation first.", 409)
    ctx = resolve_org_access(db, auth.user, org_id)
    if ctx is None:
        raise AppError("not_found", "Organisation not found.", 404)
    return ctx


def _forbidden() -> AppError:
    return AppError("forbidden", "You do not have permission to do this.", 403)


def require_role(*roles: OrgRole) -> Callable[..., OrgContext]:
    """``current_org`` plus: the caller's role must be one of ``roles``."""
    allowed = frozenset(roles)

    def dependency(ctx: OrgContext = Depends(current_org)) -> OrgContext:
        if ctx.role not in allowed:
            raise _forbidden()
        return ctx

    return dependency


def require_permission(permission: Permission) -> Callable[..., OrgContext]:
    """``current_org`` plus: the caller's role must have ``permission`` in the matrix."""

    def dependency(ctx: OrgContext = Depends(current_org)) -> OrgContext:
        if not ctx.can(permission):
            raise _forbidden()
        return ctx

    return dependency
