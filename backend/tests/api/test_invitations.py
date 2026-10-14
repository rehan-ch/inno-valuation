"""Invitations: invite by email, list, revoke, preview and accept."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_token, invitation_token_value
from app.emails.backends import MemoryEmailBackend
from app.models import AuditEvent, Invitation, Membership, Organisation, User
from app.models.enums import MembershipRole, OrganisationStatus
from app.services import invitations as invitation_service
from app.services.audit import AuditAction
from tests.api.helpers import csrf, member, signed_in, token_from
from tests.factories import InvitationFactory, verified_user

INVITATIONS = "/api/v1/organisation/invitations"
PREVIEW = "/api/v1/invitations/preview"
ACCEPT = "/api/v1/invitations/accept"
ORG = "/api/v1/organisation"


def _invite(client: TestClient, email: str, role: str = "member") -> Any:
    return client.post(INVITATIONS, json={"email": email, "role": role}, headers=csrf(client))


def _accept(client: TestClient, token: str) -> Any:
    return client.post(ACCEPT, json={"token": token}, headers=csrf(client))


def _membership(db: Session, org: Organisation, user: User) -> Membership | None:
    return db.scalar(
        select(Membership).where(
            Membership.organisation_id == org.id, Membership.user_id == user.id
        )
    )


def _invited(
    client: TestClient, outbox: MemoryEmailBackend, email: str, role: str = "member"
) -> str:
    """Invite ``email`` as the signed-in admin; returns the token from the email."""
    response = _invite(client, email, role)
    assert response.status_code == 201, response.text
    return token_from(outbox.outbox[-1])


# Inviting


def test_invite_sends_an_email_with_a_single_use_link(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    admin, org = member(MembershipRole.ADMIN, name="Ada Admin")
    signed_in(client, admin)
    response = _invite(client, "  New.Person@Example.com ", "committee")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "new.person@example.com"
    assert body["role"] == "committee"
    assert body["invited_by_name"] == "Ada Admin"
    assert body["expired"] is False

    [message] = outbox.outbox
    assert message.to == "new.person@example.com"
    assert org.name in message.text
    assert "Ada Admin" in message.text
    assert "a committee member" in message.text
    assert "7 days" in message.text
    assert "/invitations/accept#token=" in message.link

    invitation = db.get(Invitation, body["id"])
    assert invitation is not None
    token = token_from(message)
    assert invitation.token_hash == hash_token(token)
    assert token not in invitation.token_hash
    [event] = db.scalars(
        select(AuditEvent).where(AuditEvent.action == AuditAction.MEMBER_INVITED.value)
    ).all()
    assert event.details == {"role": "committee"}
    assert event.organisation_id == org.id


def test_inviting_again_replaces_the_old_link(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    old = _invited(client, outbox, "again@example.com")
    new = _invited(client, outbox, "again@example.com", "investor")
    assert old != new
    rows = client.get(INVITATIONS).json()
    assert [(r["email"], r["role"]) for r in rows] == [("again@example.com", "investor")]

    person = verified_user(email="again@example.com")
    signed_in(client, person)
    assert _accept(client, old).json()["error"]["code"] == "invalid_invitation"
    assert _accept(client, new).status_code == 200
    found = _membership(db, org, person)
    assert found is not None
    assert found.role is MembershipRole.INVESTOR


def test_only_an_owner_invites_an_owner(client: TestClient, outbox: MemoryEmailBackend) -> None:
    owner, org = member(MembershipRole.OWNER)
    admin, _ = member(MembershipRole.ADMIN, org)
    signed_in(client, admin)
    response = _invite(client, "boss@example.com", "owner")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "owner_only"
    assert outbox.outbox == []
    signed_in(client, owner)
    assert _invite(client, "boss@example.com", "owner").status_code == 201


def test_cannot_invite_an_existing_member(client: TestClient, outbox: MemoryEmailBackend) -> None:
    admin, org = member(MembershipRole.ADMIN)
    existing, _ = member(MembershipRole.MEMBER, org)
    signed_in(client, admin)
    response = _invite(client, existing.email.upper())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_member"
    assert outbox.outbox == []


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "role": "member"},
        {"email": "a@example.com", "role": "consultant"},
        {"email": "a@example.com"},
        {"email": "a@example.com", "role": "member", "organisation_id": "x"},
    ],
)
def test_invite_rejects_bad_input(client: TestClient, body: dict[str, Any]) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    assert client.post(INVITATIONS, json=body, headers=csrf(client)).status_code == 422


@pytest.mark.parametrize("role", [MembershipRole.MEMBER, MembershipRole.INVESTOR])
def test_non_managers_cannot_invite_or_see_invitations(
    client: TestClient, role: MembershipRole
) -> None:
    user, _ = member(role)
    signed_in(client, user)
    assert _invite(client, "x@example.com").status_code == 403
    assert client.get(INVITATIONS).status_code == 403


def test_invitations_are_limited_per_organisation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(invitation_service, "INVITE_LIMIT", 2)
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    assert _invite(client, "a@example.com").status_code == 201
    assert _invite(client, "b@example.com").status_code == 201
    assert _invite(client, "c@example.com").json()["error"]["code"] == "too_many_requests"


def test_archived_organisation_cannot_invite(client: TestClient, db: Session) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    org.status = OrganisationStatus.ARCHIVED
    db.flush()
    assert _invite(client, "a@example.com").json()["error"]["code"] == "organisation_archived"


# Listing and revoking


def test_list_shows_pending_and_expired_but_not_used_ones(client: TestClient) -> None:
    admin, org = member(MembershipRole.ADMIN)
    InvitationFactory.create(organisation=org, email="pending@example.com")
    InvitationFactory.create(
        organisation=org,
        email="expired@example.com",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    InvitationFactory.create(
        organisation=org, email="accepted@example.com", accepted_at=datetime.now(UTC)
    )
    InvitationFactory.create(
        organisation=org, email="revoked@example.com", revoked_at=datetime.now(UTC)
    )
    InvitationFactory.create(email="other-org@example.com")
    signed_in(client, admin)
    rows = {r["email"]: r for r in client.get(INVITATIONS).json()}
    assert set(rows) == {"pending@example.com", "expired@example.com"}
    assert rows["expired@example.com"]["expired"] is True
    assert rows["pending@example.com"]["expired"] is False


def test_revoke_stops_the_link(client: TestClient, db: Session, outbox: MemoryEmailBackend) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    token = _invited(client, outbox, "gone@example.com")
    [row] = client.get(INVITATIONS).json()
    response = client.delete(f"{INVITATIONS}/{row['id']}", headers=csrf(client))
    assert response.status_code == 200
    assert client.get(INVITATIONS).json() == []
    assert client.delete(f"{INVITATIONS}/{row['id']}", headers=csrf(client)).status_code == 404
    assert client.post(PREVIEW, json={"token": token}).status_code == 400

    person = verified_user(email="gone@example.com")
    signed_in(client, person)
    assert _accept(client, token).json()["error"]["code"] == "invalid_invitation"
    assert _membership(db, org, person) is None


def test_invitations_of_another_organisation_are_not_found(client: TestClient, db: Session) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    other = InvitationFactory.create(email="theirs@example.com")
    signed_in(client, admin)
    assert "theirs@example.com" not in client.get(INVITATIONS).text
    response = client.delete(f"{INVITATIONS}/{other.id}", headers=csrf(client))
    assert response.status_code == 404
    db.refresh(other)
    assert other.revoked_at is None


# Preview and accept


def test_preview_needs_only_the_token(client: TestClient, outbox: MemoryEmailBackend) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    token = _invited(client, outbox, "guest@example.com", "investor")
    client.cookies.clear()
    response = client.post(PREVIEW, json={"token": token})
    assert response.status_code == 200
    body = response.json()
    assert body["organisation_name"] == org.name
    assert body["email"] == "guest@example.com"
    assert body["role"] == "investor"


@pytest.mark.parametrize("token", ["not-a-token", "x" * 200])
def test_preview_of_an_unknown_token(client: TestClient, token: str) -> None:
    response = client.post(PREVIEW, json={"token": token})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_invitation"


def test_accept_joins_and_switches_to_the_organisation(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    token = _invited(client, outbox, "joiner@example.com", "committee")

    joiner = verified_user(email="joiner@example.com")
    signed_in(client, joiner)
    response = _accept(client, token)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["active_organisation_id"] == str(org.id)
    assert [m["role"] for m in body["memberships"]] == ["committee"]
    assert client.get(ORG).json()["role"] == "committee"

    invitation = db.scalar(select(Invitation).where(Invitation.email == "joiner@example.com"))
    assert invitation is not None
    assert invitation.accepted_at is not None
    [event] = db.scalars(
        select(AuditEvent).where(AuditEvent.action == AuditAction.INVITATION_ACCEPTED.value)
    ).all()
    assert event.actor_user_id == joiner.id
    assert event.details == {"role": "committee", "already_member": False}
    # Used once: a second click does nothing.
    assert _accept(client, token).json()["error"]["code"] == "invalid_invitation"


def test_accept_needs_the_invited_email(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    token = _invited(client, outbox, "right@example.com")
    wrong = verified_user(email="wrong@example.com")
    signed_in(client, wrong)
    response = _accept(client, token)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invitation_email_mismatch"
    assert _membership(db, org, wrong) is None
    # The link still works for the right person.
    signed_in(client, verified_user(email="right@example.com"))
    assert _accept(client, token).status_code == 200


def test_accept_needs_a_session_and_csrf(client: TestClient, outbox: MemoryEmailBackend) -> None:
    admin, _ = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    token = _invited(client, outbox, "csrf@example.com")
    client.cookies.clear()
    assert client.post(ACCEPT, json={"token": token}).status_code == 401
    signed_in(client, verified_user(email="csrf@example.com"))
    response = client.post(ACCEPT, json={"token": token})
    assert response.json()["error"]["code"] == "csrf_failed"


def test_accept_an_expired_invitation(client: TestClient, db: Session) -> None:
    _, org = member(MembershipRole.ADMIN)
    invitation = InvitationFactory.create(
        organisation=org,
        email="late@example.com",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    invitation.token_hash = hash_token(invitation_token_value(invitation.id))
    db.flush()
    person = verified_user(email="late@example.com")
    signed_in(client, person)
    assert (
        _accept(client, invitation_token_value(invitation.id)).json()["error"]["code"]
        == "invalid_invitation"
    )
    assert _membership(db, org, person) is None


def test_accept_into_an_archived_organisation(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    admin, org = member(MembershipRole.ADMIN)
    signed_in(client, admin)
    token = _invited(client, outbox, "arch@example.com")
    org.status = OrganisationStatus.ARCHIVED
    db.flush()
    signed_in(client, verified_user(email="arch@example.com"))
    assert _accept(client, token).json()["error"]["code"] == "invalid_invitation"


def test_an_existing_member_keeps_their_role(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    owner, org = member(MembershipRole.OWNER)
    signed_in(client, owner)
    token = _invited(client, outbox, "later@example.com", "investor")
    person = verified_user(email="later@example.com")
    db.add(Membership(organisation_id=org.id, user_id=person.id, role=MembershipRole.ADMIN))
    db.flush()
    signed_in(client, person)
    assert _accept(client, token).status_code == 200
    found = _membership(db, org, person)
    assert found is not None
    assert found.role is MembershipRole.ADMIN
