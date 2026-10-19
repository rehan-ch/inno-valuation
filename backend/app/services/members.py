"""The active organisation's team: list members, change a role, remove a member.

Owner rules (on top of the permission table, see docs/architecture/permissions.md):
- only an owner may give the owner role, or change or remove an owner;
- the last owner can be neither demoted nor removed.

Every change locks the organisation row and then re-reads the actor's own role, so a role
check never relies on a role that changed a moment ago.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.models import Membership, Organisation, User
from app.models.enums import MembershipRole
from app.services.audit import AuditAction, record
from app.services.organisations import lock_organisation

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})


def list_members(org: Organisation, db: Session) -> list[Membership]:
    """Members with their users, owners first, then by name."""
    return list(
        db.scalars(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organisation_id == org.id)
            .options(joinedload(Membership.user))
            .order_by(
                (Membership.role != MembershipRole.OWNER),
                func.lower(User.name),
                User.id,
            )
        )
    )


def change_role(
    org: Organisation,
    db: Session,
    *,
    ctx: OrgContext,
    membership_id: uuid.UUID,
    role: MembershipRole,
) -> Membership:
    """Give a member a new role. Commits."""
    lock_organisation(db, org)
    manager_role = actor_role(org, db, ctx)
    target = _find(org, db, membership_id)
    if role is target.role:
        return target
    if MembershipRole.OWNER in (role, target.role):
        _require_owner(manager_role)
    if target.role is MembershipRole.OWNER:
        _keep_one_owner(org, db)
    previous = target.role
    target.role = role
    record(
        db,
        AuditAction.MEMBER_ROLE_CHANGED,
        actor=ctx.user,
        organisation_id=org.id,
        target_type="user",
        target_id=target.user_id,
        details={"from": previous.value, "to": role.value},
    )
    db.commit()
    return target


def remove_member(
    org: Organisation, db: Session, *, ctx: OrgContext, membership_id: uuid.UUID
) -> None:
    """Remove a member. Access ends at once: every request re-checks the membership. Commits."""
    lock_organisation(db, org)
    manager_role = actor_role(org, db, ctx)
    target = _find(org, db, membership_id)
    if target.role is MembershipRole.OWNER:
        _require_owner(manager_role)
        _keep_one_owner(org, db)
    record(
        db,
        AuditAction.MEMBER_REMOVED,
        actor=ctx.user,
        organisation_id=org.id,
        target_type="user",
        target_id=target.user_id,
        details={"role": target.role.value},
    )
    db.delete(target)
    db.commit()


def find_membership(org: Organisation, db: Session, user_id: uuid.UUID) -> Membership | None:
    """Read from the database even when the session already holds the row
    (``populate_existing``), so a role changed by another request is never missed."""
    return db.scalar(
        select(Membership)
        .where(Membership.organisation_id == org.id, Membership.user_id == user_id)
        .execution_options(populate_existing=True)
    )


def may_give_role(
    org: Organisation, db: Session, user_id: uuid.UUID | None, role: MembershipRole
) -> bool:
    """True while ``user_id`` could still give ``role`` here: a manager, and an owner for the
    owner role. An invitation is honoured only while its sender still may give its role."""
    if user_id is None:
        return False
    membership = find_membership(org, db, user_id)
    if membership is None or membership.role not in MANAGER_ROLES:
        return False
    return role is not MembershipRole.OWNER or membership.role is MembershipRole.OWNER


def require_owner_for(manager_role: MembershipRole, role: MembershipRole) -> None:
    """Only an owner may hand out the owner role (also used for invitations)."""
    if role is MembershipRole.OWNER:
        _require_owner(manager_role)


def actor_role(org: Organisation, db: Session, ctx: OrgContext) -> MembershipRole:
    """The actor's membership role, re-read after ``lock_organisation``. 403 if it no longer
    allows managing the team."""
    membership = find_membership(org, db, ctx.user.id)
    if membership is None or membership.role not in MANAGER_ROLES:
        raise AppError("forbidden", "You do not have permission to do this.", 403)
    return membership.role


def _find(org: Organisation, db: Session, membership_id: uuid.UUID) -> Membership:
    target = db.scalar(
        select(Membership)
        .where(Membership.id == membership_id, Membership.organisation_id == org.id)
        .execution_options(populate_existing=True)
    )
    if target is None:
        raise AppError("not_found", "Member not found.", 404)
    return target


def _require_owner(manager_role: MembershipRole) -> None:
    if manager_role is not MembershipRole.OWNER:
        raise AppError("owner_only", "Only an owner can do this.", 403)


def _keep_one_owner(org: Organisation, db: Session) -> None:
    owners = db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.organisation_id == org.id, Membership.role == MembershipRole.OWNER)
    )
    if (owners or 0) <= 1:
        raise AppError(
            "last_owner",
            "An organisation needs at least one owner. Make someone else an owner first.",
            409,
        )
