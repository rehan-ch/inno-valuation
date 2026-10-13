"""Roles and permissions inside one organisation. The single place to change who may do what.

``docs/architecture/permissions.md`` mirrors ``ROLE_PERMISSIONS``; a test keeps them equal.

A member's role comes from their membership. ``consultant`` is not a membership role: it
comes from a live ``consultant_grants`` row and is read-only. Platform admins
(``users.is_platform_admin``) get nothing here; they see an organisation only as a member.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from app.models import Organisation, User
from app.models.enums import MembershipRole


class OrgRole(StrEnum):
    """The caller's role in the active organisation: a membership role or ``consultant``."""

    OWNER = MembershipRole.OWNER.value
    ADMIN = MembershipRole.ADMIN.value
    MEMBER = MembershipRole.MEMBER.value
    COMMITTEE = MembershipRole.COMMITTEE.value
    # PROVISIONAL: see open-questions Q13 (investor is a role inside one company).
    INVESTOR = MembershipRole.INVESTOR.value
    CONSULTANT = "consultant"

    @classmethod
    def from_membership(cls, role: MembershipRole) -> "OrgRole":
        return cls(role.value)


class Permission(StrEnum):
    VIEW_ORGANISATION = "organisation.view"
    EDIT_ORGANISATION = "organisation.edit"  # profile and currency
    MANAGE_MEMBERS = "members.manage"  # members and invitations
    CHANGE_ROLES = "members.change_role"
    MANAGE_CONSULTANT_ACCESS = "consultants.manage"
    VIEW_TEAM = "team.view"


_MANAGE: Final = frozenset(Permission)
_VIEW: Final = frozenset({Permission.VIEW_ORGANISATION, Permission.VIEW_TEAM})

ROLE_PERMISSIONS: Final[dict[OrgRole, frozenset[Permission]]] = {
    OrgRole.OWNER: _MANAGE,
    OrgRole.ADMIN: _MANAGE,
    OrgRole.MEMBER: _VIEW,
    OrgRole.COMMITTEE: _VIEW,
    OrgRole.INVESTOR: _VIEW,
    OrgRole.CONSULTANT: frozenset({Permission.VIEW_ORGANISATION}),
}


def has_permission(role: OrgRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


@dataclass(frozen=True)
class OrgContext:
    """Who is acting, in which organisation, with which role. Built by ``current_org``.

    Services take ``ctx.organisation`` as their first argument and filter by its id.
    """

    organisation: Organisation
    user: User
    role: OrgRole

    @property
    def organisation_id(self) -> uuid.UUID:
        return self.organisation.id

    @property
    def is_consultant(self) -> bool:
        return self.role is OrgRole.CONSULTANT

    def can(self, permission: Permission) -> bool:
        return has_permission(self.role, permission)
