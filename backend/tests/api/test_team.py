"""Creating an organisation, and the team: list members, change roles, remove members."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import OrgContext, OrgRole
from app.models import AuditEvent, Membership, Organisation
from app.models.enums import MembershipRole, OrganisationStatus
from app.services import members
from app.services import organisations as organisation_service
from app.services.audit import AuditAction
from tests.api.helpers import csrf, member, signed_in
from tests.factories import ConsultantGrantFactory, verified_user

CREATE = "/api/v1/organisations"
ORG = "/api/v1/organisation"
MEMBERS = "/api/v1/organisation/members"
ME = "/api/v1/me"


def _membership(db: Session, org: Organisation, user_id: Any) -> Membership:
    found = db.scalar(
        select(Membership).where(
            Membership.organisation_id == org.id, Membership.user_id == user_id
        )
    )
    assert found is not None
    return found


def _patch_role(client: TestClient, membership: Membership, role: str) -> Any:
    return client.patch(f"{MEMBERS}/{membership.id}", json={"role": role}, headers=csrf(client))


def _remove(client: TestClient, membership: Membership) -> Any:
    return client.delete(f"{MEMBERS}/{membership.id}", headers=csrf(client))


def _events(db: Session, action: AuditAction) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.action == action.value)))


# Create an organisation


def test_create_makes_the_creator_owner_and_the_organisation_active(
    client: TestClient, db: Session
) -> None:
    user = verified_user()
    signed_in(client, user)
    response = client.post(
        CREATE, json={"name": "  Acme Ltd ", "industry": "Retail"}, headers=csrf(client)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Acme Ltd"
    assert body["industry"] == "Retail"
    assert body["currency"] == "USD"
    assert body["role"] == "owner"

    org = db.get(Organisation, body["id"])
    assert org is not None
    assert org.created_by_user_id == user.id
    assert _membership(db, org, user.id).role is MembershipRole.OWNER
    assert client.get(ME).json()["active_organisation_id"] == body["id"]
    assert client.get(ORG).json()["id"] == body["id"]
    [event] = _events(db, AuditAction.ORGANISATION_CREATED)
    assert event.organisation_id == org.id
    assert event.actor_user_id == user.id


def test_create_with_another_currency(client: TestClient) -> None:
    signed_in(client, verified_user())
    response = client.post(
        CREATE, json={"name": "Euro Co", "currency": "EUR"}, headers=csrf(client)
    )
    assert response.json()["currency"] == "EUR"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "   "},
        {"name": "Acme", "currency": None},
        {"name": "Acme", "currency": "usd"},
        {"name": "Acme", "status": "archived"},
        {"name": "Acme", "id": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_create_rejects_bad_input(client: TestClient, body: dict[str, Any]) -> None:
    signed_in(client, verified_user())
    assert client.post(CREATE, json=body, headers=csrf(client)).status_code == 422


def test_create_needs_a_session_and_csrf(client: TestClient) -> None:
    assert client.post(CREATE, json={"name": "Acme"}).status_code == 401
    signed_in(client, verified_user())
    response = client.post(CREATE, json={"name": "Acme"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_create_is_limited_per_user(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(organisation_service, "CREATE_LIMIT", 2)
    signed_in(client, verified_user())
    for name in ("One", "Two"):
        assert client.post(CREATE, json={"name": name}, headers=csrf(client)).status_code == 201
    response = client.post(CREATE, json={"name": "Three"}, headers=csrf(client))
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_requests"
    assert response.json()["error"]["message"] == (
        "You have created 2 organisations in the last day, the most allowed. "
        "Try again in about 24 hours."
    )


# List members


def test_members_are_listed_owners_first(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER, name="Zed Owner")
    member(MembershipRole.MEMBER, org, name="Anna Member")
    member(MembershipRole.INVESTOR, org, name="bob Investor")
    member(MembershipRole.OWNER)  # another organisation
    signed_in(client, owner)
    response = client.get(MEMBERS)
    assert response.status_code == 200
    rows = response.json()
    assert [r["name"] for r in rows] == ["Zed Owner", "Anna Member", "bob Investor"]
    assert rows[0]["role"] == "owner"
    assert rows[0]["email"] == owner.email
    assert set(rows[0]) == {"id", "user_id", "name", "email", "role", "joined_at"}


@pytest.mark.parametrize("role", [MembershipRole.MEMBER, MembershipRole.COMMITTEE])
def test_every_member_can_see_the_team(client: TestClient, role: MembershipRole) -> None:
    user, _ = member(role)
    signed_in(client, user)
    assert client.get(MEMBERS).status_code == 200


# Change roles


def test_admin_changes_a_member_role(client: TestClient, db: Session) -> None:
    admin, org = member(MembershipRole.ADMIN)
    person, _ = member(MembershipRole.MEMBER, org)
    target = _membership(db, org, person.id)
    signed_in(client, admin)
    response = _patch_role(client, target, "committee")
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "committee"
    db.refresh(target)
    assert target.role is MembershipRole.COMMITTEE
    [event] = _events(db, AuditAction.MEMBER_ROLE_CHANGED)
    assert event.details == {"from": "member", "to": "committee"}
    assert event.target_id == person.id
    assert event.organisation_id == org.id


def test_setting_the_same_role_changes_nothing(client: TestClient, db: Session) -> None:
    admin, org = member(MembershipRole.ADMIN)
    person, _ = member(MembershipRole.MEMBER, org)
    signed_in(client, admin)
    assert _patch_role(client, _membership(db, org, person.id), "member").status_code == 200
    assert _events(db, AuditAction.MEMBER_ROLE_CHANGED) == []


def test_role_change_takes_effect_at_once(client: TestClient, db: Session) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    assert client.patch(ORG, json={"name": "New"}, headers=csrf(client)).status_code == 200
    _membership(db, org, admin.id).role = MembershipRole.MEMBER
    db.flush()
    response = client.patch(ORG, json={"name": "Again"}, headers=csrf(client))
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["member", "committee", "investor"])
def test_non_managers_cannot_change_roles(client: TestClient, db: Session, role: str) -> None:
    user, org = member(MembershipRole(role))
    other, _ = member(MembershipRole.MEMBER, org)
    signed_in(client, user)
    response = _patch_role(client, _membership(db, org, other.id), "admin")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_only_an_owner_gives_the_owner_role(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    admin, _ = member(MembershipRole.ADMIN, org)
    person, _ = member(MembershipRole.MEMBER, org)
    target = _membership(db, org, person.id)

    signed_in(client, admin)
    refused = _patch_role(client, target, "owner")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "owner_only"
    # An admin cannot make themselves an owner either.
    assert _patch_role(client, _membership(db, org, admin.id), "owner").status_code == 403

    signed_in(client, owner)
    assert _patch_role(client, target, "owner").status_code == 200


def test_admin_cannot_change_or_remove_an_owner(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    member(MembershipRole.OWNER, org)
    admin, _ = member(MembershipRole.ADMIN, org)
    target = _membership(db, org, owner.id)
    signed_in(client, admin)
    assert _patch_role(client, target, "member").json()["error"]["code"] == "owner_only"
    assert _remove(client, target).json()["error"]["code"] == "owner_only"
    db.refresh(target)
    assert target.role is MembershipRole.OWNER


def test_last_owner_cannot_step_down(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    target = _membership(db, org, owner.id)
    signed_in(client, owner)
    response = _patch_role(client, target, "admin")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_owner"
    assert _remove(client, target).json()["error"]["code"] == "last_owner"


def test_an_owner_steps_down_when_another_owner_exists(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    member(MembershipRole.OWNER, org)
    signed_in(client, owner)
    response = _patch_role(client, _membership(db, org, owner.id), "admin")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_role_must_be_a_membership_role(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    person, _ = member(MembershipRole.MEMBER, org)
    signed_in(client, owner)
    target = _membership(db, org, person.id)
    for role in ("consultant", "platform_admin", ""):
        assert _patch_role(client, target, role).status_code == 422


# Remove members


def test_remove_a_member_ends_their_access_at_once(client: TestClient, db: Session) -> None:
    admin, org = member(MembershipRole.ADMIN)
    person, _ = member(MembershipRole.MEMBER, org)
    target = _membership(db, org, person.id)

    signed_in(client, person)
    person_cookies = dict(client.cookies)
    assert client.get(ORG).status_code == 200

    signed_in(client, admin)
    response = _remove(client, target)
    assert response.status_code == 200, response.text
    assert db.get(Membership, target.id) is None
    [event] = _events(db, AuditAction.MEMBER_REMOVED)
    assert event.details == {"role": "member"}
    assert event.target_id == person.id

    client.cookies.clear()
    for name, value in person_cookies.items():
        client.cookies.set(name, value)
    assert client.get(ORG).status_code == 404
    assert client.get(ME).json()["active_organisation_id"] is None


def test_an_admin_can_leave(client: TestClient, db: Session) -> None:
    member(MembershipRole.OWNER)
    admin, org = member(MembershipRole.ADMIN)
    member(MembershipRole.OWNER, org)
    signed_in(client, admin)
    assert _remove(client, _membership(db, org, admin.id)).status_code == 200
    assert client.get(ORG).status_code == 404


def test_members_cannot_remove_anyone(client: TestClient, db: Session) -> None:
    user, org = member(MembershipRole.MEMBER)
    other, _ = member(MembershipRole.MEMBER, org)
    signed_in(client, user)
    assert _remove(client, _membership(db, org, other.id)).status_code == 403


def test_archived_organisation_team_is_view_only(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    person, _ = member(MembershipRole.MEMBER, org)
    signed_in(client, owner)
    org.status = OrganisationStatus.ARCHIVED
    db.flush()
    assert client.get(MEMBERS).status_code == 200
    target = _membership(db, org, person.id)
    assert _patch_role(client, target, "admin").json()["error"]["code"] == "organisation_archived"
    assert _remove(client, target).json()["error"]["code"] == "organisation_archived"


# Company separation


def test_members_of_another_organisation_are_not_found(client: TestClient, db: Session) -> None:
    owner_a, _ = member(MembershipRole.OWNER)
    person_b, org_b = member(MembershipRole.MEMBER)
    target = _membership(db, org_b, person_b.id)
    signed_in(client, owner_a)
    assert person_b.email not in client.get(MEMBERS).text
    for response in (_patch_role(client, target, "admin"), _remove(client, target)):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    db.refresh(target)
    assert target.role is MembershipRole.MEMBER


def test_consultant_cannot_see_or_change_the_team(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    consultant = verified_user()
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=consultant.email,
        consultant_user_id=consultant.id,
        accepted_at=datetime.now(UTC),
    )
    signed_in(client, consultant, org)
    assert client.get(MEMBERS).status_code == 403
    response = _patch_role(client, _membership(db, org, owner.id), "member")
    assert response.status_code == 403


def test_two_owners_cannot_both_step_down(client: TestClient, db: Session) -> None:
    """Sequential stand-in for the race: the organisation row lock makes the second request
    see the first one's change, so it is refused."""
    first, org = member(MembershipRole.OWNER)
    second, _ = member(MembershipRole.OWNER, org)
    signed_in(client, first)
    assert _patch_role(client, _membership(db, org, first.id), "admin").status_code == 200
    signed_in(client, second)
    response = _patch_role(client, _membership(db, org, second.id), "admin")
    assert response.json()["error"]["code"] == "last_owner"
    owners = db.scalars(
        select(Membership).where(
            Membership.organisation_id == org.id, Membership.role == MembershipRole.OWNER
        )
    ).all()
    assert len(owners) == 1


def test_a_demoted_admin_loses_team_powers(db: Session) -> None:
    """The actor's role is re-read inside the organisation lock, so a request that started
    while the actor was still an admin cannot act once they have been demoted."""
    admin, org = member(MembershipRole.ADMIN)
    person, _ = member(MembershipRole.MEMBER, org)
    stale = OrgContext(organisation=org, user=admin, role=OrgRole.ADMIN)
    _membership(db, org, admin.id).role = MembershipRole.MEMBER
    db.flush()
    target = _membership(db, org, person.id)
    with pytest.raises(AppError) as raised:
        members.remove_member(org, db, ctx=stale, membership_id=target.id)
    assert raised.value.code == "forbidden"
