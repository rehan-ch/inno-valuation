# Roles and permissions

One table decides who may do what inside an organisation: `ROLE_PERMISSIONS` in `backend/app/core/permissions.py`. This page mirrors it. Change both together; `tests/core/test_permissions.py` checks the code against the table below.

## Who has a role in an organisation
- A member has the role on their `memberships` row: `owner`, `admin`, `member`, `committee` or `investor` (investor is PROVISIONAL, see open-questions Q13).
- A consultant has the role `consultant` only while a live `consultant_grants` row exists for them (accepted, not revoked, `expires_at` in the future). A consultant is never a member, and the role is read-only.
- Platform staff (`users.is_platform_admin`) get nothing automatic over client data. They see an organisation only if they are also a member of it.

`current_org` re-checks the membership or grant on every request, so a removed member or an ended grant loses access at once (404 `not_found`).

## Matrix (Phase 2)

| Permission | Code | owner | admin | member | committee | investor | consultant |
|---|---|---|---|---|---|---|---|
| View the organisation | `organisation.view` | yes | yes | yes | yes | yes | yes |
| Edit organisation profile and currency | `organisation.edit` | yes | yes | no | no | no | no |
| Manage members and invitations | `members.manage` | yes | yes | no | no | no | no |
| Change roles | `members.change_role` | yes | yes | no | no | no | no |
| Manage consultant access | `consultants.manage` | yes | yes | no | no | no | no |
| View the team | `team.view` | yes | yes | yes | yes | yes | no |

Owner-only rules (for example who may make someone an owner, or remove the last owner) are decided with the members work and belong in the service layer, not in this table.

## Errors
- No valid session: 401 `not_authenticated`.
- No active organisation picked: 409 `no_active_organisation`.
- Not a member and no live grant for the active organisation: 404 `not_found` (the organisation's existence is not revealed).
- A role without the permission: 403 `forbidden`.
- Unsafe method without a matching `X-CSRF-Token` header: 403 `csrf_failed`.
