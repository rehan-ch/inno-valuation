"""The activity log over HTTP (Phase 5, P5.10): every key action is on record with who,
when, the method version and the AI model; owners and admins view, filter and export it;
nobody can change it."""

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.models.enums import MembershipRole
from app.scoring.question_set import QUESTION_SET
from app.services import audit_log
from app.services.audit import AuditAction
from tests.api.flows import (
    GOLDEN,
    IDEAS,
    UseAi,
    add_idea,
    as_user,
    confirm,
    finish_readiness,
    propose,
)
from tests.api.helpers import csrf, member
from tests.factories import AuditEventFactory, ConsultantGrantFactory, verified_user

BASE = "/api/v1/audit"


def _events(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get(BASE, params=params)
    assert response.status_code == 200, response.text
    events: list[dict[str, Any]] = response.json()["events"]
    return events


def _one(events: list[dict[str, Any]], action: AuditAction) -> dict[str, Any]:
    [event] = [e for e in events if e["action"] == action.value]
    return event


def _a_busy_day(client: TestClient, use_ai: UseAi, mia_id: str) -> None:
    """The signed-in owner does one of everything worth recording."""
    # Team and access.
    invited = client.post(
        "/api/v1/organisation/invitations",
        json={"email": "new.person@example.com", "role": "member"},
        headers=csrf(client),
    )
    assert invited.status_code == 201, invited.text
    members = client.get("/api/v1/organisation/members").json()
    mia_row = next(m for m in members if m["user_id"] == mia_id)
    changed = client.patch(
        f"/api/v1/organisation/members/{mia_row['id']}",
        json={"role": "admin"},
        headers=csrf(client),
    )
    assert changed.status_code == 200, changed.text
    granted = client.post(
        "/api/v1/organisation/consultants",
        json={
            "email": "amy@example.com",
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
        headers=csrf(client),
    )
    assert granted.status_code == 201, granted.text
    # Organisation settings, importance and targets.
    assert (
        client.patch(
            "/api/v1/organisation", json={"industry": "Retail"}, headers=csrf(client)
        ).status_code
        == 200
    )
    weights = dict.fromkeys(QUESTION_SET.dimension_keys, 1) | {"customer_journey": 3}
    assert (
        client.put("/api/v1/weights", json={"weights": weights}, headers=csrf(client)).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/targets/iq", json={"targets": {"data_intelligence": 9}}, headers=csrf(client)
        ).status_code
        == 200
    )
    # Readiness: start, submit, agree, finalise.
    finish_readiness(client)
    # An idea: add, change, score with the AI, confirm with one score changed and a reason,
    # then score it again.
    idea_id = add_idea(client, title="Golden idea")
    assert (
        client.patch(
            f"{IDEAS}/{idea_id}", json={"risks": "Adoption may be slow."}, headers=csrf(client)
        ).status_code
        == 200
    )
    assessment_id = propose(client, use_ai, idea_id)
    confirm(
        client,
        idea_id,
        assessment_id,
        {"organizational_agility": 5},
        {"organizational_agility": "The team has reorganised twice this year."},
    )
    propose(client, use_ai, idea_id)


def test_every_key_action_is_on_record(client: TestClient, use_ai: UseAi) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    mia, _ = member(MembershipRole.MEMBER, org, name="Mia Member")
    as_user(client, owner, org)
    _a_busy_day(client, use_ai, str(mia.id))

    events = _events(client, limit=200)
    recorded = {e["action"] for e in events}
    assert recorded >= {
        AuditAction.MEMBER_INVITED.value,
        AuditAction.MEMBER_ROLE_CHANGED.value,
        AuditAction.CONSULTANT_ACCESS_GRANTED.value,
        AuditAction.ORGANISATION_UPDATED.value,
        AuditAction.WEIGHTS_CHANGED.value,
        AuditAction.TARGETS_CHANGED.value,
        AuditAction.READINESS_STARTED.value,
        AuditAction.READINESS_RESPONSE_SUBMITTED.value,
        AuditAction.READINESS_CONSENSUS_STARTED.value,
        AuditAction.READINESS_FINALISED.value,
        AuditAction.IDEA_CREATED.value,
        AuditAction.IDEA_UPDATED.value,
        AuditAction.IQ_REQUESTED.value,
        AuditAction.IQ_CONFIRMED.value,
    }
    # Who and when, newest first.
    assert {e["actor_name"] for e in events} == {"Olive Owner"}
    assert {e["actor_id"] for e in events} == {str(owner.id)}
    times = [e["at"] for e in events]
    assert times == sorted(times, reverse=True)
    assert all(e["action_label"] != e["action"] for e in events)  # every action has words

    role = _one(events, AuditAction.MEMBER_ROLE_CHANGED)
    assert (role["action_label"], role["subject"], role["detail"]) == (
        "Role changed",
        "Mia Member",
        "From member to admin.",
    )
    assert _one(events, AuditAction.MEMBER_INVITED)["subject"] == "new.person@example.com"
    assert _one(events, AuditAction.CONSULTANT_ACCESS_GRANTED)["subject"] == "amy@example.com"
    assert _one(events, AuditAction.ORGANISATION_UPDATED)["detail"] == "Changed: industry."
    assert (
        _one(events, AuditAction.WEIGHTS_CHANGED)["detail"]
        == "Importance changed for: Customer Journey."
    )
    assert (
        _one(events, AuditAction.TARGETS_CHANGED)["detail"]
        == "Idea (IQ) targets changed for: Data Intelligence."
    )
    assert (
        _one(events, AuditAction.READINESS_CONSENSUS_STARTED)["detail"]
        == "1 person had submitted answers."
    )
    # Method version on the readiness events.
    for action in (AuditAction.READINESS_STARTED, AuditAction.READINESS_FINALISED):
        assert _one(events, action)["question_set_version"] == QUESTION_SET.version

    # AI suggestions and re-runs, with the model asked.
    requested = [e for e in events if e["action"] == AuditAction.IQ_REQUESTED.value]
    assert [e["detail"] for e in requested] == ["Scored again.", "First scoring of this idea."]
    assert {e["subject"] for e in requested} == {"Golden idea"}
    assert all(e["ai_model"] and e["question_set_version"] == 1 for e in requested)
    # The confirmation: what changed, that a reason is on record, method version, model.
    confirmed = _one(events, AuditAction.IQ_CONFIRMED)
    assert confirmed["subject"] == "Golden idea"
    assert confirmed["detail"] == (
        "Changed from the AI's proposal: Organizational Agility. "
        "A note is on record for: Organizational Agility."
    )
    assert confirmed["question_set_version"] == QUESTION_SET.version
    assert confirmed["ai_model"] == GOLDEN["replies"][0]["model"]
    # Nothing the log must never hold: scores, the idea's text, the reason itself.
    everything = str(events)
    assert "reorganised twice" not in everything
    assert "Adoption may be slow" not in everything
    assert GOLDEN["idea"]["summary"] not in everything


def test_keeping_every_proposed_score_is_recorded_as_such(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    idea_id = add_idea(client)
    confirm(client, idea_id, propose(client, use_ai, idea_id))
    confirmed = _one(_events(client), AuditAction.IQ_CONFIRMED)
    assert confirmed["detail"] == "Every proposed score was kept."


def test_the_log_filters_by_action_and_by_person(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    admin, _ = member(MembershipRole.ADMIN, org, name="Adam Admin")
    as_user(client, owner, org)
    add_idea(client, title="Olive's idea")
    client.put(
        "/api/v1/targets/iq", json={"targets": {"customer_journey": 8}}, headers=csrf(client)
    )
    as_user(client, admin, org)
    add_idea(client, title="Adam's idea")

    filters = client.get(f"{BASE}/filters")
    assert filters.status_code == 200, filters.text
    assert filters.json() == {
        "actions": [
            {"action": "idea.created", "label": "Idea added"},
            {"action": "targets.changed", "label": "Targets changed"},
        ],
        "actors": [
            {"id": str(admin.id), "name": "Adam Admin"},
            {"id": str(owner.id), "name": "Olive Owner"},
        ],
    }
    assert [e["subject"] for e in _events(client, action="idea.created")] == [
        "Adam's idea",
        "Olive's idea",
    ]
    by_olive = _events(client, actor_id=str(owner.id))
    assert {e["actor_name"] for e in by_olive} == {"Olive Owner"}
    assert len(by_olive) == 2
    both = _events(client, action="idea.created", actor_id=str(admin.id))
    assert [e["subject"] for e in both] == ["Adam's idea"]
    assert _events(client, action="member.removed") == []
    assert client.get(BASE, params={"actor_id": "not-a-uuid"}).status_code == 422


def test_the_log_pages_with_a_cursor(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for minute in range(7):
        AuditEventFactory.create(
            organisation_id=org.id,
            actor_user_id=owner.id,
            action=AuditAction.IDEA_CREATED.value,
            # Two events share each timestamp, so the id has to break the tie.
            created_at=start + timedelta(minutes=minute // 2),
        )
    as_user(client, owner, org)

    seen: list[str] = []
    before: str | None = None
    pages = 0
    while True:
        params: dict[str, Any] = {"limit": 3}
        if before:
            params["before"] = before
        body = client.get(BASE, params=params).json()
        seen.extend(e["id"] for e in body["events"])
        pages += 1
        before = body["next_before"]
        if before is None:
            break
    assert pages == 3
    assert len(seen) == len(set(seen)) == 7
    expected = [
        str(e.id)
        for e in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.organisation_id == org.id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        )
    ]
    assert seen == expected

    bad = client.get(BASE, params={"before": "not-a-cursor"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_cursor"
    assert client.get(BASE, params={"limit": 0}).status_code == 422
    assert client.get(BASE, params={"limit": audit_log.MAX_PAGE_SIZE + 1}).status_code == 422


def test_the_export_is_the_same_list_as_a_csv_file(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    as_user(client, owner, org)
    add_idea(client, title='=HYPERLINK("http://evil.example","Click")')
    client.put(
        "/api/v1/targets/iq", json={"targets": {"customer_journey": 8}}, headers=csrf(client)
    )

    response = client.get(f"{BASE}/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="activity-log.csv"'
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "Time (UTC)",
        "Person",
        "Action",
        "About",
        "Details",
        "Question set version",
        "AI model",
    ]
    assert [(r[1], r[2]) for r in rows[1:]] == [
        ("Olive Owner", "Targets changed"),
        ("Olive Owner", "Idea added"),
    ]
    assert rows[1][4] == "Idea (IQ) targets changed for: Customer Journey."
    assert rows[1][5] == str(QUESTION_SET.version)
    # A title that would run as a formula in a spreadsheet is written as text.
    assert rows[2][3] == '\'=HYPERLINK("http://evil.example","Click")'

    filtered = client.get(f"{BASE}/export", params={"action": "idea.created"})
    assert len(list(csv.reader(io.StringIO(filtered.text)))) == 2


def test_someone_who_left_stays_in_the_log_without_a_name(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    gone, _ = member(MembershipRole.ADMIN, org, name="Gone Person")
    as_user(client, gone, org)
    add_idea(client)
    as_user(client, owner, org)
    db.delete(db.get(type(gone), gone.id))
    db.commit()

    [event] = _events(client, action="idea.created")
    assert (event["actor_id"], event["actor_name"]) == (None, None)
    assert client.get(f"{BASE}/filters").json()["actors"] == []
    rows = list(csv.reader(io.StringIO(client.get(f"{BASE}/export").text)))
    assert "Someone who has left" in [r[1] for r in rows[1:]]


def test_only_owners_and_admins_see_the_log(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    add_idea(client)
    admin, _ = member(MembershipRole.ADMIN, org)
    as_user(client, admin, org)
    assert len(_events(client)) == 1

    consultant = verified_user()
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=consultant.email,
        consultant_user_id=consultant.id,
        accepted_at=datetime.now(UTC),
    )
    people = [
        member(role, org)[0]
        for role in (MembershipRole.MEMBER, MembershipRole.COMMITTEE, MembershipRole.INVESTOR)
    ]
    for person in [*people, consultant]:
        as_user(client, person, org)
        for path in (BASE, f"{BASE}/filters", f"{BASE}/export"):
            refused = client.get(path)
            assert refused.status_code == 403, (person.email, path)
            assert refused.json()["error"]["code"] == "forbidden"

    client.cookies.clear()
    assert client.get(BASE).status_code == 401


def test_another_organisations_events_and_personal_events_never_show(
    client: TestClient,
) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    as_user(client, owner, org)  # signing in is recorded without an organisation
    add_idea(client, title="Ours")

    outsider, other = member(MembershipRole.OWNER, name="Otto Outsider")
    as_user(client, outsider, other)
    add_idea(client, title="Theirs")
    assert [e["subject"] for e in _events(client)] == ["Theirs"]
    assert [a["name"] for a in client.get(f"{BASE}/filters").json()["actors"]] == ["Otto Outsider"]
    assert _events(client, actor_id=str(owner.id)) == []
    assert "Ours" not in client.get(f"{BASE}/export").text

    as_user(client, owner, org)
    events = _events(client)
    assert [e["subject"] for e in events] == ["Ours"]
    assert "user.signed_in" not in {e["action"] for e in events}


def test_nobody_can_change_or_delete_an_event(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    add_idea(client)
    [event] = _events(client)
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        for path in (BASE, f"{BASE}/{event['id']}"):
            response = client.request(method, path, json={}, headers=csrf(client))
            assert response.status_code in (404, 405), (method, path, response.status_code)
    assert [e["id"] for e in _events(client)] == [event["id"]]
    assert db.get(AuditEvent, event["id"]) is not None
