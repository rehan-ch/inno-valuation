"""Company separation and role checks, proven on the active organisation's profile."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, ConsultantGrant, Membership, Organisation
from app.models.enums import MembershipRole, OrganisationStatus
from app.services.audit import AuditAction
from tests.api.helpers import csrf, member, signed_in
from tests.factories import (
    ConsultantGrantFactory,
    MembershipFactory,
    OrganisationFactory,
    verified_user,
)

ORG = "/api/v1/organisation"
ACTIVE = "/api/v1/me/active-organisation"


def _patch(client: TestClient, body: dict[str, Any]) -> Any:
    return client.patch(ORG, json=body, headers=csrf(client))


def test_member_sees_the_active_organisation(client: TestClient) -> None:
    user, org = member(MembershipRole.INVESTOR)
    signed_in(client, user)
    response = client.get(ORG)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(org.id)
    assert body["name"] == org.name
    assert body["currency"] == "USD"
    assert body["role"] == "investor"


def test_no_active_organisation(client: TestClient) -> None:
    signed_in(client, verified_user())
    response = client.get(ORG)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_active_organisation"


def test_unauthenticated(client: TestClient) -> None:
    assert client.get(ORG).json()["error"]["code"] == "not_authenticated"


# Company separation


def test_user_of_a_cannot_reach_organisation_b(client: TestClient) -> None:
    user_a, org_a = member(MembershipRole.OWNER)
    _, org_b = member(MembershipRole.OWNER)
    signed_in(client, user_a)

    switch = client.post(ACTIVE, json={"organisation_id": str(org_b.id)}, headers=csrf(client))
    assert switch.status_code == 404
    assert switch.json()["error"]["code"] == "not_found"
    assert client.get(ORG).json()["id"] == str(org_a.id)
    # An organisation id elsewhere in the request gives no authority.
    response = client.get(ORG, params={"organisation_id": str(org_b.id)})
    assert response.json()["id"] == str(org_a.id)
    edit = _patch(client, {"name": "Renamed"})
    assert edit.json()["id"] == str(org_a.id)


def test_patch_body_cannot_name_another_organisation(client: TestClient, db: Session) -> None:
    user_a, _ = member(MembershipRole.OWNER)
    _, org_b = member(MembershipRole.OWNER)
    signed_in(client, user_a)
    response = _patch(client, {"id": str(org_b.id), "name": "Hijacked"})
    assert response.status_code == 422
    db.refresh(org_b)
    assert org_b.name != "Hijacked"


def test_removed_member_loses_access_immediately(client: TestClient, db: Session) -> None:
    user, _ = member(MembershipRole.ADMIN)
    signed_in(client, user)
    assert client.get(ORG).status_code == 200
    db.execute(delete(Membership).where(Membership.user_id == user.id))
    db.flush()
    response = client.get(ORG)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_role_change_applies_immediately(client: TestClient, db: Session) -> None:
    user, _ = member(MembershipRole.ADMIN)
    signed_in(client, user)
    assert _patch(client, {"name": "As admin"}).status_code == 200
    membership = db.scalars(select(Membership).where(Membership.user_id == user.id)).one()
    membership.role = MembershipRole.MEMBER
    db.flush()
    assert _patch(client, {"name": "As member"}).status_code == 403


def test_disabled_user_loses_access_immediately(client: TestClient, db: Session) -> None:
    user, _ = member(MembershipRole.OWNER)
    signed_in(client, user)
    user.is_active = False
    db.flush()
    assert client.get(ORG).status_code == 401


def test_platform_admin_gets_nothing_automatic(client: TestClient) -> None:
    _, org = member(MembershipRole.OWNER)
    admin = verified_user(is_platform_admin=True)
    signed_in(client, admin)
    switch = client.post(ACTIVE, json={"organisation_id": str(org.id)}, headers=csrf(client))
    assert switch.status_code == 404


# Roles


@pytest.mark.parametrize("role", [MembershipRole.OWNER, MembershipRole.ADMIN])
def test_owner_and_admin_edit_the_profile(
    client: TestClient, db: Session, role: MembershipRole
) -> None:
    user, org = member(role)
    signed_in(client, user)
    response = _patch(
        client,
        {
            "name": "  Acme Ltd ",
            "currency": "EUR",
            "country": "GB",
            "website": "https://acme.example.com",
            "description": "   ",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Acme Ltd"
    assert body["currency"] == "EUR"
    assert body["description"] is None
    db.refresh(org)
    assert (org.name, org.currency, org.country) == ("Acme Ltd", "EUR", "GB")
    [event] = db.scalars(
        select(AuditEvent).where(AuditEvent.action == AuditAction.ORGANISATION_UPDATED.value)
    )
    assert event.organisation_id == org.id
    assert event.actor_user_id == user.id
    # Field names only, never the company's values.
    assert event.details == {"fields": ["country", "currency", "name", "website"]}


@pytest.mark.parametrize(
    "role", [MembershipRole.MEMBER, MembershipRole.COMMITTEE, MembershipRole.INVESTOR]
)
def test_other_roles_cannot_edit_the_profile(
    client: TestClient, db: Session, role: MembershipRole
) -> None:
    user, org = member(role)
    signed_in(client, user)
    response = _patch(client, {"name": "Changed"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    db.refresh(org)
    assert org.name != "Changed"
    assert client.get(ORG).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"name": None},
        {"name": " "},
        {"currency": None},
        {"currency": "usd"},
        {"currency": "US"},
        {"country": "gbr"},
        {"website": "javascript:alert(1)"},
        {"primary_contact_email": "nope"},
        {"status": "archived"},
    ],
)
def test_profile_validation(client: TestClient, body: dict[str, Any]) -> None:
    user, _ = member(MembershipRole.OWNER)
    signed_in(client, user)
    assert _patch(client, body).status_code == 422


def test_profile_edit_needs_csrf(client: TestClient) -> None:
    user, _ = member(MembershipRole.OWNER)
    signed_in(client, user)
    response = client.patch(ORG, json={"name": "No token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


# Consultant access through a live grant (read-only)


def _grant(org: Organisation, **overrides: Any) -> ConsultantGrant:
    consultant = verified_user()
    values: dict[str, Any] = {
        "organisation": org,
        "consultant_email": consultant.email,
        "consultant_user_id": consultant.id,
        "accepted_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ConsultantGrantFactory.create(**values)


def _consultant_signs_in(client: TestClient, db: Session, grant: ConsultantGrant) -> Any:
    from app.models import User  # noqa: PLC0415

    consultant = db.get(User, grant.consultant_user_id)
    assert consultant is not None
    signed_in(client, consultant)
    return client.post(
        ACTIVE, json={"organisation_id": str(grant.organisation_id)}, headers=csrf(client)
    )


def test_consultant_with_live_grant_can_view_but_not_edit(client: TestClient, db: Session) -> None:
    _, org = member(MembershipRole.OWNER)
    grant = _grant(org)
    assert _consultant_signs_in(client, db, grant).status_code == 200
    view = client.get(ORG)
    assert view.status_code == 200
    assert view.json()["role"] == "consultant"
    assert _patch(client, {"name": "Consultant edit"}).status_code == 403


@pytest.mark.parametrize(
    "overrides",
    [
        {"accepted_at": None},
        {"revoked_at": datetime.now(UTC)},
        {"expires_at": datetime.now(UTC) - timedelta(minutes=1)},
    ],
)
def test_consultant_without_live_grant_gets_404(
    client: TestClient, db: Session, overrides: dict[str, Any]
) -> None:
    _, org = member(MembershipRole.OWNER)
    grant = _grant(org, **overrides)
    assert _consultant_signs_in(client, db, grant).status_code == 404


def test_ended_grant_loses_access_immediately(client: TestClient, db: Session) -> None:
    _, org = member(MembershipRole.OWNER)
    grant = _grant(org)
    _consultant_signs_in(client, db, grant)
    assert client.get(ORG).status_code == 200
    grant.revoked_at = datetime.now(UTC)
    db.flush()
    assert client.get(ORG).status_code == 404


def test_new_organisation_is_not_visible_to_unrelated_users(client: TestClient) -> None:
    OrganisationFactory.create(name="Hidden Co")
    user, _ = member(MembershipRole.OWNER)
    signed_in(client, user)
    assert "Hidden Co" not in client.get("/api/v1/me").text


# Archived organisations are view-only until the archive feature exists


def test_archived_organisation_cannot_be_chosen(client: TestClient) -> None:
    user, live = member(MembershipRole.OWNER)
    archived = OrganisationFactory.create(status=OrganisationStatus.ARCHIVED)
    MembershipFactory.create(user=user, organisation=archived, role=MembershipRole.OWNER)
    signed_in(client, user)
    response = client.post(ACTIVE, json={"organisation_id": str(archived.id)}, headers=csrf(client))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "organisation_archived"
    statuses = {
        m["organisation_id"]: m["organisation_status"]
        for m in client.get("/api/v1/me").json()["memberships"]
    }
    assert statuses == {str(live.id): "active", str(archived.id): "archived"}


def test_only_archived_membership_is_not_picked_at_sign_in(client: TestClient) -> None:
    archived = OrganisationFactory.create(status=OrganisationStatus.ARCHIVED)
    user, _ = member(MembershipRole.OWNER, organisation=archived)
    signed_in(client, user)
    assert client.get("/api/v1/me").json()["active_organisation_id"] is None


def test_archived_while_active_is_view_only(client: TestClient, db: Session) -> None:
    user, org = member(MembershipRole.OWNER)
    signed_in(client, user)
    org.status = OrganisationStatus.ARCHIVED
    db.flush()
    view = client.get(ORG)
    assert view.status_code == 200
    assert view.json()["status"] == "archived"
    edit = _patch(client, {"name": "Changed"})
    assert edit.status_code == 403
    assert edit.json()["error"]["code"] == "organisation_archived"


def test_archived_check_does_not_hide_a_missing_role(client: TestClient, db: Session) -> None:
    user, org = member(MembershipRole.MEMBER)
    signed_in(client, user)
    org.status = OrganisationStatus.ARCHIVED
    db.flush()
    assert _patch(client, {"name": "Changed"}).json()["error"]["code"] == "forbidden"
