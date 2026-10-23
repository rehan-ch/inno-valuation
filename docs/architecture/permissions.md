# Roles and permissions

One table decides who may do what inside an organisation: `ROLE_PERMISSIONS` in `backend/app/core/permissions.py`. This page mirrors it. Change both together; `tests/core/test_permissions.py` checks the code against the table below.

## Who has a role in an organisation
- A member has the role on their `memberships` row: `owner`, `admin`, `member`, `committee` or `investor` (investor is PROVISIONAL, see open-questions Q13).
- A consultant has the role `consultant` only while a live `consultant_grants` row exists for them (accepted, not revoked, `expires_at` in the future). A consultant is never a member, and the role is read-only.
- Platform staff (`users.is_platform_admin`) get nothing automatic over client data. They see an organisation only if they are also a member of it.

`current_org` re-checks the membership or grant on every request, so a removed member or an ended grant loses access at once (404 `not_found`).

An archived organisation is view-only until the archive feature exists (Phase 8): it cannot be chosen as the active organisation, and only `organisation.view` and `team.view` still work. `require_permission(...)` enforces this; `require_role(...)` checks the role only, so routes that change data use `require_permission(...)`.

## Matrix (Phases 2 and 3)

| Permission | Code | owner | admin | member | committee | investor | consultant |
|---|---|---|---|---|---|---|---|
| View the organisation | `organisation.view` | yes | yes | yes | yes | yes | yes |
| Edit organisation profile and currency | `organisation.edit` | yes | yes | no | no | no | no |
| Manage members and invitations | `members.manage` | yes | yes | no | no | no | no |
| Change roles | `members.change_role` | yes | yes | no | no | no | no |
| Manage consultant access | `consultants.manage` | yes | yes | no | no | no | no |
| View the team | `team.view` | yes | yes | yes | yes | yes | no |
| View assessments and results | `assessments.view` | yes | yes | yes | yes | yes | yes |
| Answer a readiness assessment | `assessments.answer` | yes | yes | yes | yes | no | no |
| Manage assessments (start, consensus, finalise) | `assessments.manage` | yes | yes | no | no | no | no |

An investor watches: they see assessments and results but do not answer. A consultant (Amy) reads assessments and results only while their grant is live; the service layer additionally limits consultants to assessments that are `final`.

## Owner rules (service layer, `app/services/members.py`)
- Only an owner may give the owner role (by role change or invitation), change an owner's role, or remove an owner. An admin gets 403 `owner_only`.
- The last owner can be neither demoted nor removed: 409 `last_owner`.
- Every team change (roles, removals, invitations, consultant access) locks the organisation row and re-reads the actor's own role first, so two people acting at once cannot leave the organisation without an owner, and a role removed a moment ago no longer counts.
- Any member who may manage the team may remove themselves, unless they are the last owner. Members without that permission cannot leave on their own yet.

## Errors
- No valid session: 401 `not_authenticated`.
- No active organisation picked: 409 `no_active_organisation`.
- Not a member and no live grant for the active organisation: 404 `not_found` (the organisation's existence is not revealed).
- A role without the permission: 403 `forbidden`.
- An owner-only action by an admin: 403 `owner_only`. Demoting or removing the last owner: 409 `last_owner`.
- A member, invitation or grant id from another organisation: 404 `not_found`.
- An edit in an archived organisation: 403 `organisation_archived`. Choosing an archived organisation as the active one: 409 `organisation_archived`.
- Unsafe method without a matching `X-CSRF-Token` header: 403 `csrf_failed`.
