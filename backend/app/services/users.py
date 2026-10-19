"""The signed-in user's own account: profile, memberships and the active organisation."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.models import ConsultantGrant, Membership, Organisation, User
from app.services.access import resolve_org_access
from app.services.audit import AuditAction, record


def list_memberships(db: Session, user: User) -> list[Membership]:
    """The user's memberships with their organisations, ordered by organisation name."""
    return list(
        db.scalars(
            select(Membership)
            .join(Organisation, Organisation.id == Membership.organisation_id)
            .where(Membership.user_id == user.id)
            .options(joinedload(Membership.organisation))
            .order_by(Organisation.name, Organisation.id)
        )
    )


def list_consultant_organisations(db: Session, user: User) -> list[ConsultantGrant]:
    """The user's accepted, live consultant access, one per organisation (the latest end
    date), with organisations loaded, ordered by organisation name. Organisations the user
    is a member of are left out: there the membership decides."""
    grants = db.scalars(
        select(ConsultantGrant)
        .join(Organisation, Organisation.id == ConsultantGrant.organisation_id)
        .where(
            ConsultantGrant.consultant_user_id == user.id,
            ConsultantGrant.accepted_at.is_not(None),
            ConsultantGrant.revoked_at.is_(None),
            ConsultantGrant.expires_at > datetime.now(UTC),
            ~exists().where(
                Membership.organisation_id == ConsultantGrant.organisation_id,
                Membership.user_id == user.id,
            ),
        )
        .options(joinedload(ConsultantGrant.organisation))
        .order_by(Organisation.name, Organisation.id, ConsultantGrant.expires_at.desc())
    )
    latest: dict[uuid.UUID, ConsultantGrant] = {}
    for grant in grants:
        latest.setdefault(grant.organisation_id, grant)
    return list(latest.values())


def update_name(db: Session, user: User, *, name: str) -> User:
    user.name = name
    db.commit()
    return user


def choose_active_organisation(
    db: Session, user: User, *, organisation_id: uuid.UUID
) -> OrgContext:
    """Check the user may act in the organisation. 404 if not, so its existence stays hidden."""
    ctx = resolve_org_access(db, user, organisation_id)
    if ctx is None:
        raise AppError("not_found", "Organisation not found.", 404)
    if ctx.is_archived:
        raise AppError(
            "organisation_archived", "This organisation is archived and cannot be opened.", 409
        )
    return ctx


def active_organisation_id(
    db: Session, user: User, organisation_id: uuid.UUID | None
) -> uuid.UUID | None:
    """The session's active organisation if the user can still reach it, else None."""
    if organisation_id is None or resolve_org_access(db, user, organisation_id) is None:
        return None
    return organisation_id


def disable_user(db: Session, user: User, *, actor: User | None) -> None:
    """Disable an account and end all of its sessions (for the Phase 8 admin panel).

    Re-enabling later does not revive old sessions: the session version has moved on, so
    the user must sign in again.
    """
    user.is_active = False
    user.session_version += 1
    record(db, AuditAction.USER_DISABLED, actor=actor, target_type="user", target_id=user.id)
    db.commit()
