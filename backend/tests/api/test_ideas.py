"""Ideas and IQ assessments over HTTP: add, score, review, confirm (spec 3, 5, 7; Amy Q1, Q7).

The golden flow is P4.09: a recorded proposal whose 12 scores add up to 83, the owner
changes Organizational Agility from 4 to 5, and the result is IQ 70.0 with Value for Money
714.29 for an investment of 50,000. No live AI call anywhere.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, IqAssessment, IqDimensionScore, Organisation, User
from app.models.enums import MembershipRole
from app.scoring.question_set import QUESTION_SET
from app.services.audit import AuditAction
from tests.ai.support import RecordedAiClient, fixture, recorded_replies
from tests.api.helpers import csrf, member, signed_in
from tests.factories import ConsultantGrantFactory, IdeaFactory, verified_user

UseAi = Callable[..., RecordedAiClient]

BASE = "/api/v1/ideas"
GOLDEN = fixture("propose_iq_scores", "typical")


def _as(client: TestClient, user: User, org: Organisation) -> None:
    client.cookies.clear()
    signed_in(client, user, org)


def _idea_body(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        **GOLDEN["idea"],
        "investment": "50000.00",
        "expected_value": "200000",
    }
    body.update(changes)
    return body


def _create(client: TestClient, **changes: Any) -> httpx2.Response:
    response: httpx2.Response = client.post(BASE, json=_idea_body(**changes), headers=csrf(client))
    return response


def _patch(client: TestClient, idea_id: str, body: dict[str, Any]) -> httpx2.Response:
    response: httpx2.Response = client.patch(f"{BASE}/{idea_id}", json=body, headers=csrf(client))
    return response


def _post(client: TestClient, path: str) -> httpx2.Response:
    response: httpx2.Response = client.post(f"{BASE}/{path}", headers=csrf(client))
    return response


def _review(
    client: TestClient,
    idea_id: str,
    assessment_id: str,
    scores: dict[str, Any] | None = None,
    notes: dict[str, Any] | None = None,
) -> httpx2.Response:
    response: httpx2.Response = client.patch(
        f"{BASE}/{idea_id}/assessments/{assessment_id}/review",
        json={"scores": scores or {}, "notes": notes or {}},
        headers=csrf(client),
    )
    return response


def _score(client: TestClient, idea_id: str) -> dict[str, Any]:
    """Send the idea for scoring and return the assessment, proposal ready."""
    response = _post(client, f"{idea_id}/assessments")
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


# The golden flow (P4.09)


def _golden_proposal(client: TestClient, org: Organisation, person: User) -> dict[str, Any]:
    """``person`` adds the golden idea and sends it for scoring; the recorded proposal
    (12 scores adding up to 83) comes back ready."""
    _as(client, person, org)
    created = _create(client)
    assert created.status_code == 201, created.text
    return _score(client, created.json()["id"])


def test_a_member_adds_an_idea_and_gets_a_proposal_to_review(
    client: TestClient, use_ai: UseAi
) -> None:
    ai = use_ai(*recorded_replies(GOLDEN))
    mia, org = member(MembershipRole.MEMBER, name="Mia Member")
    _as(client, mia, org)
    created = _create(client)
    assert created.status_code == 201, created.text
    idea = created.json()
    assert idea["status"] == "draft"
    assert idea["investment"] == "50000.00"
    assert idea["currency"] == "USD"  # the organisation's currency
    assert idea["can_change"] is True
    assert idea["can_archive"] is False
    assert idea["latest_assessment"] is None

    proposal = _score(client, idea["id"])
    assert proposal["status"] == "proposed"
    assert proposal["proposal_status"] == "ready"
    assert proposal["sample"] is False
    assert proposal["iq"] is None
    assert proposal["can_review"] is True
    assert len(ai.requests) == 1
    assert "50000" not in ai.requests[0].user  # money never reaches the model
    by_key = {d["key"]: d for d in proposal["dimensions"]}
    assert by_key["organizational_agility"]["proposed_score"] == 4
    assert by_key["organizational_agility"]["final_score"] is None
    assert len(by_key["organizational_agility"]["proposed_rationale"]) == 2
    assert by_key["organizational_agility"]["proposed_confidence"] == "0.70"
    assert proposal["missing_information"] == GOLDEN["replies"][0]["output"]["missing_information"]
    assert client.get(f"{BASE}/{idea['id']}").json()["status"] == "submitted"

    # The owner of the idea changes one score, with a reason, saved as they go.
    reviewed = _review(
        client,
        idea["id"],
        proposal["id"],
        {"organizational_agility": 5},
        {"organizational_agility": "The team has reorganised twice this year."},
    )
    assert reviewed.status_code == 200, reviewed.text
    row = next(d for d in reviewed.json()["dimensions"] if d["key"] == "organizational_agility")
    assert (row["proposed_score"], row["final_score"], row["changed"]) == (4, 5, True)
    assert row["note"] == "The team has reorganised twice this year."


def test_changing_organizational_agility_to_5_gives_iq_70_and_vfm_714_29(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    use_ai(*recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    mia, _ = member(MembershipRole.MEMBER, org, name="Mia Member")
    proposal = _golden_proposal(client, org, mia)
    idea_id = proposal["idea_id"]
    _review(client, idea_id, proposal["id"], {"organizational_agility": 5})

    confirmed = _post(client, f"{idea_id}/assessments/{proposal['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["status"] == "confirmed"
    assert result["iq"] == "70.0"
    assert result["iq_maximum"] == "100.0"
    assert result["vfm"] == {
        "investment": "50000.00",
        "currency": "USD",
        "per_point": "714.29",
        "not_calculable_reason": None,
    }
    # Category IQ = mean of its dimension scores x 10 (spec 3.6).
    assert {c["key"]: c["score"] for c in result["categories"]} == {
        "customer_facing": "74.0",
        "process": "55.0",
        "strategic": "72.0",
    }
    # Lowest five, ties in book order (spec 7), each with the book's next steps.
    assert [(p["key"], p["score"]) for p in result["priorities"]] == [
        ("organizational_agility", 5),
        ("sustainable_future", 5),
        ("channel_navigation", 6),
        ("operational_efficiency", 6),
        ("brand_magnetism", 7),
    ]
    assert result["priorities"][0]["level_name"] == "Innovation"
    assert (
        result["priorities"][0]["next_steps"]
        == QUESTION_SET.dimension("organizational_agility").next_steps
    )
    levels = {d["key"]: d["level"]["name"] for d in result["dimensions"]}
    assert levels["organizational_agility"] == "Innovation"
    assert levels["product_evolution"] == "Invention"
    assert result["confirmed_by_name"] == "Mia Member"
    assert result["can_review"] is False

    # The list shows the headline numbers to everyone in the organisation.
    _as(client, owner, org)
    listed = client.get(BASE).json()
    assert listed[0]["status"] == "assessed"
    assert listed[0]["latest_assessment"]["iq"] == "70.0"
    assert listed[0]["latest_assessment"]["vfm_per_point"] == "714.29"

    actions = [e.action for e in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at))]
    assert AuditAction.IQ_REQUESTED.value in actions
    confirmed_event = db.scalar(
        select(AuditEvent).where(AuditEvent.action == AuditAction.IQ_CONFIRMED.value)
    )
    assert confirmed_event is not None
    assert confirmed_event.details == {"changed": ["organizational_agility"]}


def test_accepting_the_proposal_unchanged_gives_the_proposed_iq(
    client: TestClient, use_ai: UseAi
) -> None:
    use_ai(*recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client, investment=None).json()
    proposal = _score(client, idea["id"])
    result = _post(client, f"{idea['id']}/assessments/{proposal['id']}/confirm").json()
    assert result["iq"] == "69.2"  # 83 / 120 x 100, rounded once to 1 decimal
    assert all(d["changed"] is False for d in result["dimensions"])
    assert result["vfm"]["per_point"] is None
    assert result["vfm"]["not_calculable_reason"] == "No investment was given for this idea."


# Immutability and history (spec 9)


def test_a_confirmed_assessment_cannot_change_and_scoring_again_keeps_it(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    use_ai(*recorded_replies(GOLDEN), *recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    first = _score(client, idea["id"])
    assert _post(client, f"{idea['id']}/assessments/{first['id']}/confirm").status_code == 200

    assert _review(client, idea["id"], first["id"], {"customer_journey": 1}).status_code == 409
    assert _post(client, f"{idea['id']}/assessments/{first['id']}/confirm").status_code == 409
    stored = db.get(IqAssessment, first["id"])
    assert stored is not None
    assert str(stored.iq) == "69.2"

    second = _score(client, idea["id"])
    assert second["id"] != first["id"]
    detail = client.get(f"{BASE}/{idea['id']}").json()
    assert detail["status"] == "submitted"
    assert [a["status"] for a in detail["assessments"]] == ["proposed", "confirmed"]
    assert client.get(f"{BASE}/{idea['id']}/assessments/{first['id']}").json()["iq"] == "69.2"


def test_scoring_again_before_confirming_supersedes_the_old_proposal(
    client: TestClient, use_ai: UseAi
) -> None:
    use_ai(*recorded_replies(GOLDEN), *recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    first = _score(client, idea["id"])
    second = _score(client, idea["id"])
    detail = client.get(f"{BASE}/{idea['id']}").json()
    assert {a["id"]: a["status"] for a in detail["assessments"]} == {
        first["id"]: "superseded",
        second["id"]: "proposed",
    }
    assert _review(client, idea["id"], first["id"], {"customer_journey": 1}).status_code == 409


def test_a_failed_proposal_can_be_asked_for_again(client: TestClient, use_ai: UseAi) -> None:
    failed = fixture("propose_iq_scores", "adversarial_obeyed")
    use_ai(*recorded_replies(failed), *recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    first = _score(client, idea["id"])
    assert first["proposal_status"] == "failed"
    assert first["dimensions"][0]["proposed_score"] is None
    assert _review(client, idea["id"], first["id"], {"customer_journey": 1}).status_code == 409
    assert _post(client, f"{idea['id']}/assessments/{first['id']}/confirm").status_code == 409
    second = _score(client, idea["id"])
    assert second["proposal_status"] == "ready"


def test_an_idea_whose_proposal_failed_can_be_changed_again(
    client: TestClient, use_ai: UseAi
) -> None:
    """A failed proposal must not leave the idea stuck in "submitted": it is a draft again,
    while a proposal on its way or waiting for review still blocks edits."""
    failed = fixture("propose_iq_scores", "adversarial_obeyed")
    use_ai(*recorded_replies(failed), *recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    first = _score(client, idea["id"])
    assert first["proposal_status"] == "failed"
    assert client.get(f"{BASE}/{idea['id']}").json()["status"] == "submitted"

    changed = _patch(client, idea["id"], {"title": "Sharper title"})
    assert changed.status_code == 200, changed.text
    assert (changed.json()["title"], changed.json()["status"]) == ("Sharper title", "draft")

    second = _score(client, idea["id"])
    assert second["proposal_status"] == "ready"
    waiting = _patch(client, idea["id"], {"title": "Too late"})
    assert waiting.status_code == 409
    assert "waiting for review" in waiting.json()["error"]["message"]


# Review rules


def test_review_notes_have_a_length_limit(client: TestClient, use_ai: UseAi) -> None:
    use_ai(*recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    proposal = _score(client, idea["id"])
    too_long = _review(client, idea["id"], proposal["id"], notes={"customer_journey": "x" * 2001})
    assert too_long.status_code == 422
    kept = _review(client, idea["id"], proposal["id"], notes={"customer_journey": " y" * 1000})
    assert kept.status_code == 200, kept.text
    note = next(d for d in kept.json()["dimensions"] if d["key"] == "customer_journey")["note"]
    assert note == ("y " * 1000).strip()


def test_review_scores_must_be_on_the_scale(client: TestClient, use_ai: UseAi) -> None:
    use_ai(*recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    proposal = _score(client, idea["id"])
    assert _review(client, idea["id"], proposal["id"], {"customer_journey": 11}).status_code == 422
    assert _review(client, idea["id"], proposal["id"], {"customer_journey": 0}).status_code == 422
    assert _review(client, idea["id"], proposal["id"], {"made_up": 5}).status_code == 422
    assert _review(client, idea["id"], proposal["id"], {"customer_journey": "7"}).status_code == 422
    # Null puts the proposal back.
    changed = _review(client, idea["id"], proposal["id"], {"customer_journey": 3}).json()
    assert next(d for d in changed["dimensions"] if d["key"] == "customer_journey")["changed"]
    back = _review(client, idea["id"], proposal["id"], {"customer_journey": None}).json()
    row = next(d for d in back["dimensions"] if d["key"] == "customer_journey")
    assert (row["final_score"], row["changed"]) == (None, False)


def test_without_an_ai_key_the_proposal_is_a_marked_sample(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    proposal = _score(client, idea["id"])
    assert proposal["sample"] is True
    assert {d["proposed_score"] for d in proposal["dimensions"]} == {5}
    result = _post(client, f"{idea['id']}/assessments/{proposal['id']}/confirm").json()
    assert result["iq"] == "50.0"
    assert result["sample"] is True


# Editing


def test_the_idea_can_be_edited_until_it_is_sent_for_scoring(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    edited = _patch(client, idea["id"], {"title": "Better title", "risks": None, "stage": "pilot"})
    assert edited.status_code == 200, edited.text
    assert (edited.json()["title"], edited.json()["risks"], edited.json()["stage"]) == (
        "Better title",
        None,
        "pilot",
    )
    assert _patch(client, idea["id"], {"title": ""}).status_code == 422
    assert _patch(client, idea["id"], {"summary": None}).status_code == 422
    assert _patch(client, idea["id"], {"made_up": "x"}).status_code == 422


def test_money_keeps_the_currencys_decimals(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assert _create(client, investment="50000.005").status_code == 422  # too many for USD
    assert _create(client, investment="-1").status_code == 422
    idea = _create(client, investment="50000.5", currency="JPY").status_code
    assert idea == 422  # yen have no decimals
    created = _create(client, investment="1234.5", expected_value=None).json()
    assert created["investment"] == "1234.50"
    # Changing the currency keeps the amount's value when it fits the new currency.
    changed = _patch(client, created["id"], {"currency": "EUR"}).json()
    assert (changed["currency"], changed["investment"]) == ("EUR", "1234.50")
    assert _patch(client, created["id"], {"currency": "JPY"}).status_code == 422
    whole = _patch(client, created["id"], {"currency": "JPY", "investment": "1235"}).json()
    assert (whole["currency"], whole["investment"]) == ("JPY", "1235")


def test_an_idea_being_scored_waits_before_it_can_change(client: TestClient, use_ai: UseAi) -> None:
    use_ai(*recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    _score(client, idea["id"])
    # The proposal is ready but not confirmed: the idea is still "submitted".
    assert _patch(client, idea["id"], {"title": "Changed"}).status_code == 409


# Who may do what


def test_a_member_changes_only_their_own_ideas_and_an_admin_any(client: TestClient) -> None:
    admin, org = member(MembershipRole.ADMIN)
    mia, _ = member(MembershipRole.MEMBER, org)
    cole, _ = member(MembershipRole.COMMITTEE, org)
    _as(client, mia, org)
    mine = _create(client).json()
    _as(client, cole, org)
    assert client.get(f"{BASE}/{mine['id']}").json()["can_change"] is False
    assert _patch(client, mine["id"], {"title": "Cole's title"}).status_code == 403
    assert _post(client, f"{mine['id']}/assessments").status_code == 403
    assert _post(client, f"{mine['id']}/archive").status_code == 403
    _as(client, admin, org)
    assert client.get(f"{BASE}/{mine['id']}").json()["can_archive"] is True
    assert _patch(client, mine["id"], {"title": "Admin's title"}).status_code == 200


def test_an_investor_watches_and_a_consultant_sees_assessed_ideas_only(
    client: TestClient, use_ai: UseAi
) -> None:
    use_ai(*recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    investor, _ = member(MembershipRole.INVESTOR, org)
    amy = verified_user(email="amy@example.com")
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=amy.email,
        consultant_user_id=amy.id,
        accepted_at=datetime.now(UTC),
    )
    _as(client, owner, org)
    draft = _create(client, title="Still a draft").json()
    scored = _create(client, title="Scored idea").json()
    proposal = _score(client, scored["id"])
    _post(client, f"{scored['id']}/assessments/{proposal['id']}/confirm")

    _as(client, investor, org)
    assert _create(client).status_code == 403
    assert {i["title"] for i in client.get(BASE).json()} == {"Still a draft", "Scored idea"}
    assert client.get(f"{BASE}/{draft['id']}").json()["can_change"] is False

    _as(client, amy, org)
    assert [i["title"] for i in client.get(BASE).json()] == ["Scored idea"]
    assert client.get(f"{BASE}/{draft['id']}").status_code == 404
    assert client.get(f"{BASE}/{scored['id']}/assessments/{proposal['id']}").json()["iq"] == "69.2"
    assert _create(client).status_code == 403


def test_a_consultant_keeps_seeing_a_confirmed_idea_while_it_is_scored_again(
    client: TestClient, use_ai: UseAi
) -> None:
    """Scoring again puts the idea back to "submitted"; the consultant still sees it, with
    the confirmed assessment as its latest, and never the new proposal."""
    use_ai(*recorded_replies(GOLDEN), *recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    amy = verified_user(email="amy@example.com")
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=amy.email,
        consultant_user_id=amy.id,
        accepted_at=datetime.now(UTC),
    )
    _as(client, owner, org)
    idea = _create(client).json()
    first = _score(client, idea["id"])
    _post(client, f"{idea['id']}/assessments/{first['id']}/confirm")
    second = _score(client, idea["id"])
    assert second["status"] == "proposed"

    _as(client, amy, org)
    listed = client.get(BASE).json()
    assert [i["id"] for i in listed] == [idea["id"]]
    assert listed[0]["latest_assessment"]["id"] == first["id"]
    detail = client.get(f"{BASE}/{idea['id']}").json()
    assert detail["latest_assessment"]["iq"] == "69.2"
    assert [a["id"] for a in detail["assessments"]] == [first["id"]]
    assert client.get(f"{BASE}/{idea['id']}/assessments/{second['id']}").status_code == 404


def test_another_organisation_sees_nothing(client: TestClient, use_ai: UseAi) -> None:
    use_ai(*recorded_replies(GOLDEN))
    one, org_one = member(MembershipRole.OWNER)
    two, org_two = member(MembershipRole.OWNER)
    _as(client, one, org_one)
    idea = _create(client).json()
    proposal = _score(client, idea["id"])
    _as(client, two, org_two)
    assert client.get(BASE).json() == []
    assert client.get(f"{BASE}/{idea['id']}").status_code == 404
    assert client.get(f"{BASE}/{idea['id']}/assessments/{proposal['id']}").status_code == 404
    assert _patch(client, idea["id"], {"title": "Theirs"}).status_code == 404
    assert _review(client, idea["id"], proposal["id"], {"customer_journey": 1}).status_code == 404
    assert _post(client, f"{idea['id']}/assessments/{proposal['id']}/confirm").status_code == 404
    assert _post(client, f"{idea['id']}/archive").status_code == 404


def test_archived_ideas_leave_the_list_and_come_back(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    idea = _create(client).json()
    archived = _post(client, f"{idea['id']}/archive").json()
    assert archived["archived"] is True
    assert client.get(BASE).json() == []
    assert len(client.get(BASE, params={"include_archived": "true"}).json()) == 1
    assert _patch(client, idea["id"], {"title": "x"}).status_code == 409
    assert _post(client, f"{idea['id']}/assessments").status_code == 409
    assert _post(client, f"{idea['id']}/restore").json()["archived"] is False
    assert len(client.get(BASE).json()) == 1


def test_an_idea_from_a_factory_without_a_creator_is_managers_only(
    client: TestClient, db: Session
) -> None:
    admin, org = member(MembershipRole.ADMIN)
    mia, _ = member(MembershipRole.MEMBER, org)
    idea = IdeaFactory.create(organisation=org)
    _as(client, mia, org)
    assert _patch(client, str(idea.id), {"title": "Mine now"}).status_code == 403
    _as(client, admin, org)
    assert _patch(client, str(idea.id), {"title": "Admin's"}).status_code == 200
    assert db.scalar(select(IqDimensionScore)) is None


@pytest.mark.parametrize("path", ["", "/{id}", "/{id}/assessments/{id}"])
def test_reading_needs_a_session(client: TestClient, path: str) -> None:
    fake = "00000000-0000-0000-0000-000000000000"
    assert client.get(BASE + path.replace("{id}", fake)).status_code == 401
