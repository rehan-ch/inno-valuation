"""Consultant access: the client's admin grants, changes and revokes it; the consultant
accepts it and then sees the organisation read-only until it ends."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.emails.backends import MemoryEmailBackend
from app.models import AuditEvent, ConsultantGrant, User
from app.models.enums import MembershipRole, OrganisationStatus
from app.services import consultant_access
from app.services.audit import AuditAction
from tests.api.helpers import csrf, member, session_cookies, signed_in, use_cookies
from tests.factories import ConsultantGrantFactory, MembershipFactory, verified_user

GRANTS = "/api/v1/organisation/consultants"
MY_ACCESS = "/api/v1/me/consultant-access"
ACTIVE = "/api/v1/me/active-organisation"
ORG = "/api/v1/organisation"
ME = "/api/v1/me"


def _in(days: float) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


def _grant(client: TestClient, email: str, ends: datetime | None = None) -> Any:
    body = {"email": email, "expires_at": (ends or _in(30)).isoformat()}
    return client.post(GRANTS, json=body, headers=csrf(client))


def _accept(client: TestClient, grant_id: str) -> Any:
    return client.post(f"{MY_ACCESS}/{grant_id}/accept", headers=csrf(client))


def _events(db: Session, action: AuditAction) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.action == action.value)))


def _granted_and_accepted(
    client: TestClient, admin: User, consultant: User, ends: datetime | None = None
) -> str:
    """Admin grants, consultant accepts. Leaves the consultant signed in. Returns the id."""
    signed_in(client, admin)
    grant_id: str = _grant(client, consultant.email, ends).json()["id"]
    signed_in(client, consultant)
    assert _accept(client, grant_id).status_code == 200
    return grant_id


# The client's side


def test_grant_emails_the_consultant(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    admin, org = member(MembershipRole.ADMIN, name="Ada Admin")
    signed_in(client, admin)
    ends = datetime(2099, 3, 5, 23, 59, tzinfo=UTC)
    response = _grant(client, " Amy@Example.com ", ends)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "amy@example.com"
    assert body["status"] == "waiting"
    assert body["accepted_at"] is None

    [message] = outbox.outbox
    assert message.to == "amy@example.com"
    assert org.name in message.text
    assert "Ada Admin" in message.text
    assert "5 March 2099" in message.text
    assert message.link.endswith("/consultant-access")
    assert "#" not in message.link  # no token: the verified email is the proof

    [event] = _events(db, AuditAction.CONSULTANT_ACCESS_GRANTED)
    assert event.organisation_id == org.id
    assert event.target_id is not None


def test_owner_can_grant_too(client: TestClient) -> None:
    owner, _ = member(MembershipRole.OWNER)
    signed_in(client, owner)
    assert _grant(client, "amy@example.com").status_code == 201


@pytest.mark.parametrize(
    "role", [MembershipRole.MEMBER, MembershipRole.COMMITTEE, MembershipRole.INVESTOR]
)
def test_only_owners_and_admins_manage_access(client: TestClient, role: MembershipRole) -> None:
    user, org = member(role)
    grant = ConsultantGrantFactory.create(organisation=org)
    signed_in(client, user)
    assert _grant(client, "amy@example.com").status_code == 403
    assert client.get(GRANTS).status_code == 403
    assert client.delete(f"{GRANTS}/{grant.id}", headers=csrf(client)).status_code == 403


def test_end_date_must_be_in_the_future(client: TestClient) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    response = _grant(client, "amy@example.com", _in(-1))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_end_date"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "amy@example.com"},
        {"email": "amy@example.com", "expires_at": "2099-01-01T00:00:00"},  # no time zone
        {"email": "amy@example.com", "expires_at": "soon"},
        {"email": "nope", "expires_at": "2099-01-01T00:00:00Z"},
        {"email": "amy@example.com", "expires_at": "2099-01-01T00:00:00Z", "scope": "all"},
    ],
)
def test_grant_rejects_bad_input(client: TestClient, body: dict[str, Any]) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    assert client.post(GRANTS, json=body, headers=csrf(client)).status_code == 422


def test_cannot_grant_a_member(client: TestClient) -> None:
    admin, org = member(MembershipRole.ADMIN)
    existing, _ = member(MembershipRole.MEMBER, org)
    signed_in(client, admin)
    assert _grant(client, existing.email).json()["error"]["code"] == "already_member"


def test_one_open_grant_per_email(client: TestClient) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    first = _grant(client, "amy@example.com").json()
    response = _grant(client, "AMY@example.com")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "access_exists"
    # After revoking, access can be given again.
    client.delete(f"{GRANTS}/{first['id']}", headers=csrf(client))
    assert _grant(client, "amy@example.com").status_code == 201


def test_grants_are_limited_per_organisation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(consultant_access, "GRANT_LIMIT", 1)
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    assert _grant(client, "a@example.com").status_code == 201
    assert _grant(client, "b@example.com").json()["error"]["code"] == "too_many_requests"


def test_list_shows_every_status(client: TestClient) -> None:
    admin, org = member(MembershipRole.ADMIN)
    now = datetime.now(UTC)
    consultant = verified_user()
    ConsultantGrantFactory.create(organisation=org, consultant_email="waiting@example.com")
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=consultant.email,
        consultant_user_id=consultant.id,
        accepted_at=now,
    )
    ConsultantGrantFactory.create(
        organisation=org, consultant_email="ended@example.com", expires_at=now - timedelta(1)
    )
    ConsultantGrantFactory.create(
        organisation=org, consultant_email="revoked@example.com", revoked_at=now
    )
    ConsultantGrantFactory.create(consultant_email="other-org@example.com")
    signed_in(client, admin)
    rows = {r["email"]: r["status"] for r in client.get(GRANTS).json()}
    assert rows == {
        "waiting@example.com": "waiting",
        consultant.email: "active",
        "ended@example.com": "ended",
        "revoked@example.com": "revoked",
    }


def test_change_the_end_date(client: TestClient, db: Session) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    grant_id = _grant(client, "amy@example.com").json()["id"]
    later = _in(90)
    response = client.patch(
        f"{GRANTS}/{grant_id}", json={"expires_at": later.isoformat()}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()["expires_at"]) == later
    assert len(_events(db, AuditAction.CONSULTANT_ACCESS_CHANGED)) == 1
    past = client.patch(
        f"{GRANTS}/{grant_id}", json={"expires_at": _in(-1).isoformat()}, headers=csrf(client)
    )
    assert past.json()["error"]["code"] == "invalid_end_date"


def test_ended_or_revoked_access_cannot_be_changed(client: TestClient) -> None:
    admin, org = member(MembershipRole.ADMIN)
    ended = ConsultantGrantFactory.create(organisation=org, expires_at=_in(-1))
    revoked = ConsultantGrantFactory.create(organisation=org, revoked_at=datetime.now(UTC))
    signed_in(client, admin)
    for grant in (ended, revoked):
        response = client.patch(
            f"{GRANTS}/{grant.id}", json={"expires_at": _in(10).isoformat()}, headers=csrf(client)
        )
        assert response.json()["error"]["code"] == "access_ended"


def test_revoking_twice_records_once(client: TestClient, db: Session) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    grant_id = _grant(client, "amy@example.com").json()["id"]
    for _ in range(2):
        response = client.delete(f"{GRANTS}/{grant_id}", headers=csrf(client))
        assert response.status_code == 200
        assert response.json()["status"] == "revoked"
    assert len(_events(db, AuditAction.CONSULTANT_ACCESS_REVOKED)) == 1


def test_grants_of_another_organisation_are_not_found(client: TestClient, db: Session) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    theirs = ConsultantGrantFactory.create(consultant_email="theirs@example.com")
    signed_in(client, admin)
    assert "theirs@example.com" not in client.get(GRANTS).text
    patch = client.patch(
        f"{GRANTS}/{theirs.id}", json={"expires_at": _in(5).isoformat()}, headers=csrf(client)
    )
    delete = client.delete(f"{GRANTS}/{theirs.id}", headers=csrf(client))
    assert patch.status_code == delete.status_code == 404
    db.refresh(theirs)
    assert theirs.revoked_at is None


def test_archived_organisation_cannot_grant(client: TestClient, db: Session) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    org.status = OrganisationStatus.ARCHIVED
    db.flush()
    assert _grant(client, "amy@example.com").json()["error"]["code"] == "organisation_archived"


# The consultant's side


def test_consultant_sees_waiting_access_and_accepts(client: TestClient, db: Session) -> None:
    admin, org = member(MembershipRole.ADMIN)
    amy = verified_user(email="amy@example.com")
    signed_in(client, admin)
    grant_id = _grant(client, "amy@example.com").json()["id"]

    signed_in(client, amy)
    [waiting] = client.get(MY_ACCESS).json()
    assert waiting["id"] == grant_id
    assert waiting["status"] == "waiting"
    assert waiting["organisation_name"] == org.name
    # Not usable before accepting.
    assert client.get(ME).json()["consultant_organisations"] == []
    switch = client.post(ACTIVE, json={"organisation_id": str(org.id)}, headers=csrf(client))
    assert switch.status_code == 404

    accepted = _accept(client, grant_id)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "active"
    grant = db.get(ConsultantGrant, grant_id)
    assert grant is not None
    assert grant.consultant_user_id == amy.id
    [event] = _events(db, AuditAction.CONSULTANT_ACCESS_ACCEPTED)
    assert event.actor_user_id == amy.id
    assert event.organisation_id == org.id

    [listed] = client.get(ME).json()["consultant_organisations"]
    assert listed["organisation_id"] == str(org.id)
    assert (
        client.post(ACTIVE, json={"organisation_id": str(org.id)}, headers=csrf(client)).status_code
        == 200
    )
    body = client.get(ORG).json()
    assert body["id"] == str(org.id)
    assert body["role"] == "consultant"
    # Read-only.
    edit = client.patch(ORG, json={"name": "Changed"}, headers=csrf(client))
    assert edit.status_code == 403
    assert _accept(client, grant_id).status_code == 404  # already accepted


def test_access_for_another_email_is_hidden(client: TestClient) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    grant_id = _grant(client, "amy@example.com").json()["id"]
    signed_in(client, verified_user(email="mallory@example.com"))
    assert client.get(MY_ACCESS).json() == []
    response = _accept(client, grant_id)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_revoked_access_ends_at_once(client: TestClient) -> None:
    admin, org = member(MembershipRole.ADMIN)
    amy = verified_user()
    grant_id = _granted_and_accepted(client, admin, amy)
    signed_in(client, amy, org)
    amy_cookies = session_cookies(client)
    assert client.get(ORG).status_code == 200

    signed_in(client, admin)
    client.delete(f"{GRANTS}/{grant_id}", headers=csrf(client))

    use_cookies(client, amy_cookies)
    assert client.get(ORG).status_code == 404
    me = client.get(ME).json()
    assert me["active_organisation_id"] is None
    assert me["consultant_organisations"] == []
    assert client.get(MY_ACCESS).json() == []


def test_ended_access_gives_nothing(client: TestClient, db: Session) -> None:
    admin, org = member(MembershipRole.ADMIN)
    amy = verified_user()
    grant_id = _granted_and_accepted(client, admin, amy)
    signed_in(client, amy, org)
    grant = db.get(ConsultantGrant, grant_id)
    assert grant is not None
    grant.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert client.get(ORG).status_code == 404
    assert client.get(ME).json()["consultant_organisations"] == []
    assert client.get(MY_ACCESS).json() == []


def test_waiting_access_that_ended_cannot_be_accepted(client: TestClient) -> None:
    _, org = member(MembershipRole.ADMIN)
    amy = verified_user()
    grant = ConsultantGrantFactory.create(
        organisation=org, consultant_email=amy.email, expires_at=_in(-1)
    )
    signed_in(client, amy)
    assert _accept(client, str(grant.id)).status_code == 404


def test_a_shortened_end_date_applies_at_once(client: TestClient) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    amy = verified_user()
    grant_id = _granted_and_accepted(client, admin, amy)
    signed_in(client, admin)
    soon = datetime.now(UTC) + timedelta(seconds=2)
    client.patch(
        f"{GRANTS}/{grant_id}", json={"expires_at": soon.isoformat()}, headers=csrf(client)
    )
    signed_in(client, amy)
    [listed] = client.get(ME).json()["consultant_organisations"]
    assert datetime.fromisoformat(listed["access_ends_at"]) <= soon


def test_a_member_cannot_accept_consultant_access(client: TestClient, db: Session) -> None:
    _, org = member(MembershipRole.ADMIN)
    person, _ = member(MembershipRole.MEMBER, org)
    grant = ConsultantGrantFactory.create(organisation=org, consultant_email=person.email)
    signed_in(client, person)
    response = _accept(client, str(grant.id))
    assert response.json()["error"]["code"] == "already_member"


def test_accept_needs_csrf(client: TestClient) -> None:
    _, org = member(MembershipRole.ADMIN)
    amy = verified_user()
    grant = ConsultantGrantFactory.create(organisation=org, consultant_email=amy.email)
    signed_in(client, amy)
    response = client.post(f"{MY_ACCESS}/{grant.id}/accept")
    assert response.json()["error"]["code"] == "csrf_failed"


def test_switcher_lists_each_organisation_once_and_skips_member_ones(client: TestClient) -> None:
    now = datetime.now(UTC)
    amy = verified_user()
    _, org_a = member(MembershipRole.ADMIN)
    _, org_b = member(MembershipRole.ADMIN)
    for org, ends in ((org_a, _in(10)), (org_a, _in(20)), (org_b, _in(5))):
        ConsultantGrantFactory.create(
            organisation=org,
            consultant_email=amy.email,
            consultant_user_id=amy.id,
            accepted_at=now,
            expires_at=ends,
        )
    MembershipFactory.create(organisation=org_b, user=amy, role=MembershipRole.MEMBER)
    signed_in(client, amy)
    listed = client.get(ME).json()["consultant_organisations"]
    assert [row["organisation_id"] for row in listed] == [str(org_a.id)]
    assert datetime.fromisoformat(listed[0]["access_ends_at"]) > _in(15)
