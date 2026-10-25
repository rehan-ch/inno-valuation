"""Readiness assessments over HTTP: answer, agree, finalise (spec 2, Amy Q5)."""

from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Organisation, ReadinessResult, User
from app.models.enums import MembershipRole, OrganisationStatus
from app.scoring.question_set import QUESTION_SET
from app.services.audit import AuditAction
from tests.api.helpers import csrf, member, signed_in
from tests.factories import ConsultantGrantFactory, verified_user

BASE = "/api/v1/readiness"
QUESTION_IDS = QUESTION_SET.all_question_ids()


def _as(client: TestClient, user: User, org: Organisation) -> None:
    client.cookies.clear()
    signed_in(client, user, org)


def _start(client: TestClient) -> httpx2.Response:
    response: httpx2.Response = client.post(f"{BASE}/assessments", headers=csrf(client))
    return response


def _answer(client: TestClient, assessment_id: str, answers: dict[str, Any]) -> httpx2.Response:
    response: httpx2.Response = client.patch(
        f"{BASE}/assessments/{assessment_id}/my-answers",
        json={"answers": answers},
        headers=csrf(client),
    )
    return response


def _submit(client: TestClient, assessment_id: str) -> httpx2.Response:
    return _post(client, assessment_id, "my-answers/submit")


def _post(client: TestClient, assessment_id: str, action: str) -> httpx2.Response:
    response: httpx2.Response = client.post(
        f"{BASE}/assessments/{assessment_id}/{action}", headers=csrf(client)
    )
    return response


def _agree(
    client: TestClient,
    assessment_id: str,
    answers: dict[str, Any],
    notes: dict[str, Any] | None = None,
) -> httpx2.Response:
    response: httpx2.Response = client.patch(
        f"{BASE}/assessments/{assessment_id}/consensus",
        json={"answers": answers, "notes": notes or {}},
        headers=csrf(client),
    )
    return response


def _all(value: int) -> dict[str, int]:
    return dict.fromkeys(QUESTION_IDS, value)


def _total_190() -> dict[str, int]:
    """Golden example (P3.07): 50 answers of 3 and 10 of 4 make 190, band Building Blocks.

    The 4s fill the first two dimensions, so those score 20 and the other ten score 15.
    """
    answers = _all(3)
    for question_id in QUESTION_IDS[:10]:
        answers[question_id] = 4
    return answers


def _assert_golden_190(result: dict[str, Any]) -> None:
    assert result["total"] == 190
    assert result["total_maximum"] == 300
    assert result["band"] == {
        "key": "building_blocks",
        "name": "Building Blocks",
        "text": "You have a strong foundation but may need to focus on specific weaknesses.",
    }
    scores = {d["key"]: d["score"] for d in result["dimensions"]}
    assert scores["customer_journey"] == 20
    assert scores["brand_magnetism"] == 20
    assert scores["financial_imperative"] == 15
    # Category = sum of its dimension scores, shown with the maximum (spec 2.6: 125, 50, 125).
    assert {c["key"]: (c["score"], c["maximum"]) for c in result["categories"]} == {
        "customer_facing": (85, 125),
        "process": (30, 50),
        "strategic": (75, 125),
    }
    # Lowest 5, ties in book order (spec 7), each with the book's next steps.
    assert [p["key"] for p in result["priorities"]] == [
        "channel_navigation",
        "service_excellence",
        "product_evolution",
        "operational_efficiency",
        "organizational_agility",
    ]
    assert (
        result["priorities"][0]["next_steps"]
        == QUESTION_SET.dimension("channel_navigation").next_steps
    )
    # Strengths score above every priority: the tied 15s are never strengths.
    assert [s["key"] for s in result["strengths"]] == ["customer_journey", "brand_magnetism"]
    assert result["submitted_count"] == 3


# The whole flow


def test_three_people_answer_the_facilitator_agrees_and_the_result_is_190(
    client: TestClient, db: Session
) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    mia, _ = member(MembershipRole.MEMBER, org, name="Mia Member")
    cole, _ = member(MembershipRole.COMMITTEE, org, name="Cole Committee")

    _as(client, owner, org)
    started = _start(client)
    assert started.status_code == 201, started.text
    assessment_id = started.json()["id"]
    assert started.json()["status"] == "collecting"
    assert started.json()["question_count"] == 60

    # Each person answers on their own; the owner answers in two autosaves.
    first_half = dict(list(_all(4).items())[:30])
    assert _answer(client, assessment_id, first_half).json()["my_status"] == "in_progress"
    assert _answer(client, assessment_id, _all(4)).json()["my_answers"] == _all(4)
    assert _submit(client, assessment_id).json()["my_status"] == "submitted"
    for person, value in ((mia, 2), (cole, 3)):
        _as(client, person, org)
        assert _answer(client, assessment_id, _all(value)).status_code == 200
        assert _submit(client, assessment_id).status_code == 200

    # The facilitator sees everyone's answer, the mean (2 decimals) and the spread.
    _as(client, owner, org)
    detail = client.get(f"{BASE}/assessments/{assessment_id}").json()
    assert detail["submitted_count"] == 3
    assert {p["name"] for p in detail["participants"]} == {
        "Olive Owner",
        "Mia Member",
        "Cole Committee",
    }
    table = _post(client, assessment_id, "consensus/begin").json()
    assert sorted(table["participants"]) == ["Cole Committee", "Mia Member", "Olive Owner"]
    first = table["questions"][0]
    assert first["question_id"] == QUESTION_IDS[0]
    assert sorted(a["answer"] for a in first["answers"]) == [2, 3, 4]
    assert first["mean"] == "3.00"
    assert first["spread"] == 2
    assert first["wide_spread"] is True

    # Agreed answers, with a note, saved in two steps; then finalised.
    golden = _total_190()
    half = dict(list(golden.items())[:20])
    saved = _agree(client, assessment_id, half, {QUESTION_IDS[0]: "We agreed on 4."}).json()
    assert saved["agreed_count"] == 20
    assert saved["questions"][0]["note"] == "We agreed on 4."
    assert _agree(client, assessment_id, golden).json()["agreed_count"] == 60

    final = _post(client, assessment_id, "finalise")
    assert final.status_code == 200, final.text
    _assert_golden_190(final.json())

    # Everyone in the organisation can read the result, and the list shows it.
    _as(client, mia, org)
    assert client.get(f"{BASE}/assessments/{assessment_id}/result").json()["total"] == 190
    listed = client.get(f"{BASE}/assessments").json()
    assert listed[0]["total"] == 190
    assert listed[0]["band_name"] == "Building Blocks"

    actions = [e.action for e in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at))]
    assert actions.count(AuditAction.READINESS_RESPONSE_SUBMITTED.value) == 3
    assert AuditAction.READINESS_FINALISED.value in actions


def test_a_final_result_cannot_be_changed(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    _answer(client, assessment_id, _all(3))
    _submit(client, assessment_id)
    _post(client, assessment_id, "consensus/begin")
    _agree(client, assessment_id, _all(3))
    assert _post(client, assessment_id, "finalise").status_code == 200
    stored = db.scalar(select(ReadinessResult))
    assert stored is not None
    before = (stored.total, dict(stored.per_dimension), stored.computed_at)

    assert _agree(client, assessment_id, _all(5)).status_code == 409
    assert _post(client, assessment_id, "finalise").status_code == 409
    assert _answer(client, assessment_id, _all(5)).status_code == 409
    assert _post(client, assessment_id, "consensus/begin").status_code == 409

    db.expire_all()
    stored = db.scalar(select(ReadinessResult))
    assert stored is not None
    assert (stored.total, dict(stored.per_dimension), stored.computed_at) == before
    assert stored.total == 180
    # Every dimension ties, so none stands out as a strength.
    assert client.get(f"{BASE}/assessments/{assessment_id}/result").json()["strengths"] == []


# Answering


def test_autosave_merges_and_null_clears(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    a, b = QUESTION_IDS[0], QUESTION_IDS[1]
    _answer(client, assessment_id, {a: 2})
    _answer(client, assessment_id, {b: 5})
    assert _answer(client, assessment_id, {a: None}).json()["my_answers"] == {b: 5}


@pytest.mark.parametrize("bad", [0, 6, "3", 2.5, True])
def test_answers_off_the_scale_are_refused(client: TestClient, bad: Any) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    response = _answer(client, assessment_id, {QUESTION_IDS[0]: bad})
    assert response.status_code == 422


def test_unknown_question_ids_are_refused(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    response = _answer(client, assessment_id, {"not_a_question": 3})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_answers"


def test_submitting_needs_every_answer(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    _answer(client, assessment_id, {QUESTION_IDS[0]: 3})
    response = _submit(client, assessment_id)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "Answer every question before submitting: 59 still to answer."
    )


def test_submitted_answers_are_locked(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    _answer(client, assessment_id, _all(3))
    _submit(client, assessment_id)
    assert _answer(client, assessment_id, {QUESTION_IDS[0]: 5}).status_code == 409


# Consensus


def test_people_who_did_not_submit_are_left_out(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    late, _ = member(MembershipRole.MEMBER, org, name="Late Larry")
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    _answer(client, assessment_id, _all(4))
    _submit(client, assessment_id)
    _as(client, late, org)
    _answer(client, assessment_id, _all(1))  # never submitted

    _as(client, owner, org)
    table = _post(client, assessment_id, "consensus/begin").json()
    assert table["participants"] == ["Olive Owner"]
    assert table["questions"][0]["answers"] == [
        {"user_id": str(owner.id), "name": "Olive Owner", "answer": 4}
    ]
    # Answering is closed now, even for the late person.
    _as(client, late, org)
    assert _answer(client, assessment_id, {QUESTION_IDS[0]: 2}).status_code == 409


def test_consensus_needs_a_submission(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    response = _post(client, assessment_id, "consensus/begin")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_submissions"


def test_the_mean_rounds_halves_up_to_two_decimals(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    others = [member(MembershipRole.MEMBER, org)[0] for _ in range(2)]
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    for person, value in zip([owner, *others], (1, 2, 2), strict=True):
        _as(client, person, org)
        _answer(client, assessment_id, _all(value))
        _submit(client, assessment_id)
    _as(client, owner, org)
    first = _post(client, assessment_id, "consensus/begin").json()["questions"][0]
    assert first["mean"] == "1.67"
    assert first["spread"] == 1
    assert first["wide_spread"] is False


def test_finalising_needs_every_agreed_answer(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    _answer(client, assessment_id, _all(3))
    _submit(client, assessment_id)
    _post(client, assessment_id, "consensus/begin")
    _agree(client, assessment_id, dict(list(_all(3).items())[:59]))
    response = _post(client, assessment_id, "finalise")
    assert response.status_code == 422
    assert "1 still to agree" in response.json()["error"]["message"]


def test_one_open_assessment_at_a_time(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assert _start(client).status_code == 201
    second = _start(client)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "assessment_open"


# Who may do what


def test_a_member_answers_but_cannot_manage(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    mia, _ = member(MembershipRole.MEMBER, org)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    _as(client, mia, org)
    assert _start(client).status_code == 403
    assert _answer(client, assessment_id, {QUESTION_IDS[0]: 3}).status_code == 200
    detail = client.get(f"{BASE}/assessments/{assessment_id}").json()
    assert detail["can_manage"] is False
    assert detail["participants"] is None  # no one else's progress
    assert client.get(f"{BASE}/assessments/{assessment_id}/consensus").status_code == 403
    assert _post(client, assessment_id, "consensus/begin").status_code == 403


def test_an_investor_watches_without_answering(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    investor, _ = member(MembershipRole.INVESTOR, org)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    _as(client, investor, org)
    detail = client.get(f"{BASE}/assessments/{assessment_id}").json()
    assert detail["can_answer"] is False
    assert detail["my_status"] is None
    assert _answer(client, assessment_id, {QUESTION_IDS[0]: 3}).status_code == 403


def test_a_consultant_sees_final_results_only(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    amy = verified_user(email="amy@example.com")
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=amy.email,
        consultant_user_id=amy.id,
        accepted_at=datetime.now(UTC),
    )
    _as(client, owner, org)
    open_id = _start(client).json()["id"]

    _as(client, amy, org)
    assert client.get(f"{BASE}/assessments").json() == []
    assert client.get(f"{BASE}/assessments/{open_id}").status_code == 404

    _as(client, owner, org)
    _answer(client, open_id, _all(4))
    _submit(client, open_id)
    _post(client, open_id, "consensus/begin")
    _agree(client, open_id, _all(4))
    _post(client, open_id, "finalise")

    _as(client, amy, org)
    assert client.get(f"{BASE}/assessments/{open_id}/result").json()["total"] == 240
    assert client.get(f"{BASE}/assessments/{open_id}/consensus").status_code == 403


def test_another_organisation_gets_not_found(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    _answer(client, assessment_id, _all(3))
    _submit(client, assessment_id)

    outsider, other_org = member(MembershipRole.OWNER)
    _as(client, outsider, other_org)
    for path in ("", "/result", "/consensus"):
        assert client.get(f"{BASE}/assessments/{assessment_id}{path}").status_code == 404
    assert _answer(client, assessment_id, {QUESTION_IDS[0]: 3}).status_code == 404
    assert _post(client, assessment_id, "consensus/begin").status_code == 404
    assert client.get(f"{BASE}/assessments").json() == []


def test_the_question_set_is_served_verbatim(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    body = client.get(f"{BASE}/question-set").json()
    assert body["version"] == QUESTION_SET.version
    assert body["scale"] == {
        "min": 1,
        "max": 5,
        "labels": {"1": "Strongly Disagree", "5": "Strongly Agree"},
    }
    assert [d["key"] for d in body["dimensions"]] == list(QUESTION_SET.dimension_keys)
    first = QUESTION_SET.dimensions[0].questions[0]
    assert body["dimensions"][0]["questions"][0] == {"id": first.id, "text": first.text}
    assert sum(len(d["questions"]) for d in body["dimensions"]) == 60


# Review fixes


def _finished(client: TestClient, people: list[User], org: Organisation) -> str:
    """Everyone answers and submits; the first person agrees 3s and finalises."""
    _as(client, people[0], org)
    assessment_id: str = _start(client).json()["id"]
    for person in people:
        _as(client, person, org)
        _answer(client, assessment_id, _all(3))
        _submit(client, assessment_id)
    _as(client, people[0], org)
    _post(client, assessment_id, "consensus/begin")
    _agree(client, assessment_id, _all(3))
    assert _post(client, assessment_id, "finalise").status_code == 200
    return assessment_id


def test_the_result_keeps_its_participant_count(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    leaver, _ = member(MembershipRole.MEMBER, org)
    assessment_id = _finished(client, [owner, leaver], org)
    assert client.get(f"{BASE}/assessments/{assessment_id}/result").json()["submitted_count"] == 2

    # The leaver deletes their account; their response goes, the result does not change.
    db.delete(db.get(User, leaver.id))
    db.flush()
    assert client.get(f"{BASE}/assessments/{assessment_id}/result").json()["submitted_count"] == 2


def test_people_with_the_same_name_stay_apart(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER, name="Alex Smith")
    twin, _ = member(MembershipRole.MEMBER, org, name="Alex Smith")
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    for person, value in ((owner, 2), (twin, 5)):
        _as(client, person, org)
        _answer(client, assessment_id, _all(value))
        _submit(client, assessment_id)
    _as(client, owner, org)
    participants = client.get(f"{BASE}/assessments/{assessment_id}").json()["participants"]
    assert {p["user_id"] for p in participants} == {str(owner.id), str(twin.id)}
    answers = _post(client, assessment_id, "consensus/begin").json()["questions"][0]["answers"]
    assert {(a["user_id"], a["answer"]) for a in answers} == {(str(owner.id), 2), (str(twin.id), 5)}


def test_an_archived_organisation_keeps_your_answers_read_only(
    client: TestClient, db: Session
) -> None:
    owner, org = member(MembershipRole.OWNER)
    mia, _ = member(MembershipRole.MEMBER, org)
    _as(client, owner, org)
    assessment_id = _start(client).json()["id"]
    # Mia's session has the organisation open when it is archived.
    _as(client, mia, org)
    _answer(client, assessment_id, {QUESTION_IDS[0]: 4})
    org.status = OrganisationStatus.ARCHIVED
    db.flush()

    body = client.get(f"{BASE}/assessments/{assessment_id}").json()
    assert body["my_answers"] == {QUESTION_IDS[0]: 4}  # still her own answers
    assert body["my_status"] == "in_progress"
    assert body["can_answer"] is False  # but no longer editable
    refused = _answer(client, assessment_id, {QUESTION_IDS[1]: 3})
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "organisation_archived"
