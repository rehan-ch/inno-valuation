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
from app.models.enums import MembershipRole, OrganisationStatus


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
    VIEW_ASSESSMENTS = "assessments.view"  # assessments and their results
    ANSWER_ASSESSMENT = "assessments.answer"  # one's own readiness answers
    MANAGE_ASSESSMENTS = "assessments.manage"  # start, consensus, finalise (facilitator, Q5)


_MANAGE: Final = frozenset(Permission)
_VIEW: Final = frozenset(
    {Permission.VIEW_ORGANISATION, Permission.VIEW_TEAM, Permission.VIEW_ASSESSMENTS}
)
_PARTICIPATE: Final = _VIEW | {Permission.ANSWER_ASSESSMENT}

# What anyone may still do in an archived organisation (view-only until the archive
# feature exists; see docs/decisions.md 2026-10-13).
READ_ONLY_PERMISSIONS: Final = _VIEW

ROLE_PERMISSIONS: Final[dict[OrgRole, frozenset[Permission]]] = {
    OrgRole.OWNER: _MANAGE,
    OrgRole.ADMIN: _MANAGE,
    OrgRole.MEMBER: _PARTICIPATE,
    OrgRole.COMMITTEE: _PARTICIPATE,
    OrgRole.INVESTOR: _VIEW,
    OrgRole.CONSULTANT: frozenset({Permission.VIEW_ORGANISATION, Permission.VIEW_ASSESSMENTS}),
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

    @property
    def is_archived(self) -> bool:
        return self.organisation.status is OrganisationStatus.ARCHIVED

    def can(self, permission: Permission) -> bool:
        """The role allows it, and an archived organisation allows only viewing."""
        if self.is_archived and permission not in READ_ONLY_PERMISSIONS:
            return False
        return has_permission(self.role, permission)
