"""The permission matrix: complete, and equal to the table in docs/architecture/permissions.md."""

import re

from app.core.permissions import (
    READ_ONLY_PERMISSIONS,
    ROLE_PERMISSIONS,
    OrgRole,
    Permission,
    has_permission,
)
from app.core.settings import REPO_ROOT
from app.models.enums import MembershipRole

DOC = REPO_ROOT / "docs" / "architecture" / "permissions.md"
MANAGE = {
    Permission.EDIT_ORGANISATION,
    Permission.MANAGE_MEMBERS,
    Permission.CHANGE_ROLES,
    Permission.MANAGE_CONSULTANT_ACCESS,
    Permission.MANAGE_ASSESSMENTS,
}


def test_every_role_has_an_entry() -> None:
    assert set(ROLE_PERMISSIONS) == set(OrgRole)


def test_every_membership_role_maps_to_an_org_role() -> None:
    for role in MembershipRole:
        assert OrgRole.from_membership(role).value == role.value


def test_only_owner_and_admin_manage() -> None:
    for role in OrgRole:
        managers = role in (OrgRole.OWNER, OrgRole.ADMIN)
        for permission in MANAGE:
            assert has_permission(role, permission) is managers, (role, permission)


def test_consultant_is_read_only() -> None:
    assert ROLE_PERMISSIONS[OrgRole.CONSULTANT] == {
        Permission.VIEW_ORGANISATION,
        Permission.VIEW_ASSESSMENTS,
    }


def test_archived_organisation_keeps_viewing_only() -> None:
    # Results stay readable in an archived organisation; nothing else does.
    expected = {Permission.VIEW_ORGANISATION, Permission.VIEW_TEAM, Permission.VIEW_ASSESSMENTS}
    assert expected == READ_ONLY_PERMISSIONS


def test_platform_admin_is_not_a_role() -> None:
    assert "tech_admin" not in {role.value for role in OrgRole}
    assert "platform_admin" not in {role.value for role in OrgRole}


def _doc_matrix() -> dict[OrgRole, set[Permission]]:
    rows = [line for line in DOC.read_text().splitlines() if re.match(r"^\| .* \| `", line)]
    header = next(line for line in DOC.read_text().splitlines() if line.startswith("| Permission"))
    roles = [OrgRole(cell.strip()) for cell in header.strip("|").split("|")[2:]]
    matrix: dict[OrgRole, set[Permission]] = {role: set() for role in roles}
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        permission = Permission(cells[1].strip("`"))
        for role, cell in zip(roles, cells[2:], strict=True):
            if cell == "yes":
                matrix[role].add(permission)
    return matrix


def test_docs_table_matches_the_code() -> None:
    assert _doc_matrix() == {role: set(perms) for role, perms in ROLE_PERMISSIONS.items()}
