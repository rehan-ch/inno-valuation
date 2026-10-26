"""The signed-in user's account and the active organisation switch."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Membership
from app.models.enums import MembershipRole
from app.services.users import disable_user
from tests.api.helpers import csrf, member, signed_in
from tests.factories import MembershipFactory, OrganisationFactory, verified_user

ME = "/api/v1/me"
ACTIVE = "/api/v1/me/active-organisation"


def test_me_lists_memberships_by_organisation_name(client: TestClient) -> None:
    user = verified_user(name="Pat")
    beta = OrganisationFactory.create(name="Beta")
    alpha = OrganisationFactory.create(name="Alpha")
    MembershipFactory.create(user=user, organisation=beta, role=MembershipRole.COMMITTEE)
    MembershipFactory.create(user=user, organisation=alpha, role=MembershipRole.OWNER)
    signed_in(client, user)

    body = client.get(ME).json()
    assert body["name"] == "Pat"
    assert body["active_organisation_id"] is None
    assert [(m["organisation_name"], m["role"]) for m in body["memberships"]] == [
        ("Alpha", "owner"),
        ("Beta", "committee"),
    ]


def test_update_name(client: TestClient, db: Session) -> None:
    user = verified_user(name="Old")
    signed_in(client, user)
    response = client.patch(ME, json={"name": "  New Name  "}, headers=csrf(client))
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    db.refresh(user)
    assert user.name == "New Name"


@pytest.mark.parametrize(
    "name", ["Ada\n\nOpen this link:\nhttps://evil.example", "Ada\x00", "A\tB"]
)
def test_update_name_rejects_control_characters(client: TestClient, name: str) -> None:
    signed_in(client, verified_user(name="Kept"))
    response = client.patch(ME, json={"name": name}, headers=csrf(client))
    assert response.status_code == 422
    [detail] = response.json()["error"]["details"]
    assert detail["loc"] == ["body", "name"]
    assert "control characters" in detail["msg"]
    assert client.get(ME).json()["name"] == "Kept"


def test_update_name_rejects_blank_and_other_fields(client: TestClient) -> None:
    signed_in(client, verified_user(email="person@example.com"))
    assert client.patch(ME, json={"name": " "}, headers=csrf(client)).status_code == 422
    response = client.patch(
        ME, json={"name": "Ok", "email": "other@example.com"}, headers=csrf(client)
    )
    assert response.status_code == 422
    assert client.get(ME).json()["email"] == "person@example.com"


def test_switch_active_organisation(client: TestClient) -> None:
    user, first = member(MembershipRole.MEMBER)
    second = OrganisationFactory.create()
    MembershipFactory.create(user=user, organisation=second, role=MembershipRole.ADMIN)
    signed_in(client, user)

    response = client.post(ACTIVE, json={"organisation_id": str(second.id)}, headers=csrf(client))
    assert response.status_code == 200
    assert response.json()["active_organisation_id"] == str(second.id)
    assert client.get("/api/v1/organisation").json()["id"] == str(second.id)

    client.post(ACTIVE, json={"organisation_id": str(first.id)}, headers=csrf(client))
    assert client.get("/api/v1/organisation").json()["role"] == "member"


def test_switch_keeps_the_csrf_token(client: TestClient) -> None:
    user, _ = member(MembershipRole.MEMBER)
    other = OrganisationFactory.create()
    MembershipFactory.create(user=user, organisation=other)
    signed_in(client, user)
    before = csrf(client)
    client.post(ACTIVE, json={"organisation_id": str(other.id)}, headers=before)
    assert csrf(client) == before


def test_cannot_switch_to_an_organisation_without_access(client: TestClient) -> None:
    user, own = member(MembershipRole.OWNER)
    stranger = OrganisationFactory.create()
    signed_in(client, user)
    for org_id in (stranger.id, uuid.uuid4()):
        response = client.post(ACTIVE, json={"organisation_id": str(org_id)}, headers=csrf(client))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert client.get(ME).json()["active_organisation_id"] == str(own.id)


def test_switch_needs_csrf(client: TestClient) -> None:
    user, org = member(MembershipRole.OWNER)
    signed_in(client, user)
    response = client.post(ACTIVE, json={"organisation_id": str(org.id)})
    assert response.status_code == 403


def test_me_drops_an_active_organisation_the_user_lost(client: TestClient, db: Session) -> None:
    user, org = member(MembershipRole.MEMBER)
    signed_in(client, user)
    assert client.get(ME).json()["active_organisation_id"] == str(org.id)
    db.execute(delete(Membership).where(Membership.user_id == user.id))
    db.flush()
    assert client.get(ME).json()["active_organisation_id"] is None
    patched = client.patch(ME, json={"name": "Still here"}, headers=csrf(client))
    assert patched.json()["active_organisation_id"] is None


def test_disable_user_ends_sessions_for_good(client: TestClient, db: Session) -> None:
    user = verified_user()
    signed_in(client, user)
    disable_user(db, user, actor=None)
    assert client.get(ME).status_code == 401
    user.is_active = True  # re-enabled later by an admin
    db.flush()
    assert client.get(ME).status_code == 401  # the old session stays dead
    signed_in(client, user)
    assert client.get(ME).status_code == 200
