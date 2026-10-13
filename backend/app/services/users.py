"""The signed-in user's own account: profile, memberships and the active organisation."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.models import Membership, Organisation, User
from app.services.access import resolve_org_access


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
    return ctx
