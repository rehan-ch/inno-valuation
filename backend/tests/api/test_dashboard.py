"""The dashboard, the compass data, the drill-down and the history over HTTP (Phase 5;
spec 4, 6, 7, 8, 9).

Golden numbers: a readiness result of 190 (Building Blocks) beside an idea whose IQ is 70.0
with Value for Money 714.29. The two are returned side by side and never combined.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import IqAssessment, ReadinessAssessment
from app.models.enums import MembershipRole
from app.scoring.question_set import QUESTION_SET
from tests.api.flows import (
    GOLDEN_SCORES,
    IDEAS,
    KEYS,
    UseAi,
    add_idea,
    all_answers,
    answers_190,
    as_user,
    confirm,
    confirmed_idea,
    finish_readiness,
    propose,
)
from tests.api.helpers import csrf, member
from tests.factories import ConsultantGrantFactory, verified_user

DASHBOARD = "/api/v1/dashboard"
HISTORY = "/api/v1/history"
TARGETS = "/api/v1/targets"


def _dashboard(client: TestClient, idea_id: str | None = None) -> dict[str, Any]:
    response = client.get(DASHBOARD, params={"idea_id": idea_id} if idea_id else None)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _segments(compass: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["key"]: s for s in compass["segments"]}


def _all_keys(value: Any) -> set[str]:
    """Every field name anywhere in a JSON value."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _all_keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _all_keys(v)}
    return set()


def test_a_new_organisation_has_nothing_to_show_yet(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    assert _dashboard(client) == {"readiness": None, "ideas": [], "iq": None}


def test_readiness_and_iq_are_side_by_side_and_never_combined(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    readiness_id = finish_readiness(client, answers_190())
    idea_id, assessment_id = confirmed_idea(client, use_ai)

    body = _dashboard(client)
    readiness, iq = body["readiness"], body["iq"]

    # Readiness: out of 300 with its band, in the book's words.
    assert readiness["assessment_id"] == readiness_id
    assert (readiness["total"], readiness["total_maximum"]) == (190, 300)
    assert readiness["band"] == {
        "key": "building_blocks",
        "name": "Building Blocks",
        "text": "You have a strong foundation but may need to focus on specific weaknesses.",
    }
    # IQ: out of 100, for the selected idea.
    assert (iq["idea_id"], iq["assessment_id"]) == (idea_id, assessment_id)
    assert (iq["iq"], iq["iq_maximum"]) == ("70.0", "100.0")
    assert iq["vfm"]["per_point"] == "714.29"
    assert body["ideas"] == [
        {
            "idea_id": idea_id,
            "title": iq["idea_title"],
            "assessment_id": assessment_id,
            "iq": "70.0",
            "confirmed_at": iq["confirmed_at"],
        }
    ]
    # Spec 4: no field anywhere adds, averages or blends the two scores.
    assert set(body) == {"readiness", "ideas", "iq"}
    forbidden = {"combined", "overall", "blended", "composite", "average", "score_total"}
    assert not (_all_keys(body) & forbidden)
    assert "iq" not in readiness
    assert "total" not in iq


def test_the_readiness_compass_is_in_book_order_with_category_totals(
    client: TestClient,
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    finish_readiness(client, answers_190())
    compass = _dashboard(client)["readiness"]["compass"]

    assert compass["scale"] == "readiness"
    assert compass["question_set_version"] == QUESTION_SET.version
    assert (compass["minimum"], compass["maximum"]) == (5, 25)
    assert [s["key"] for s in compass["segments"]] == KEYS
    assert [s["order"] for s in compass["segments"]] == list(range(1, 13))
    assert [s["name"] for s in compass["segments"]] == [d.name for d in QUESTION_SET.dimensions]
    segments = _segments(compass)
    assert (segments["customer_journey"]["score"], segments["customer_journey"]["maximum"]) == (
        20,
        25,
    )
    assert segments["financial_imperative"]["score"] == 15
    # No per-dimension label exists for readiness (open-questions Q4), so none is invented.
    assert {s["level"] for s in compass["segments"]} == {None}
    assert compass["levels"] == []
    # Categories in order, each with the sum of its dimensions and its maximum (spec 2.6).
    assert [(c["key"], c["score"], c["maximum"]) for c in compass["categories"]] == [
        ("customer_facing", "85", "125"),
        ("process", "30", "50"),
        ("strategic", "75", "125"),
    ]
    assert compass["categories"][1]["dimension_keys"] == [
        "operational_efficiency",
        "organizational_agility",
    ]
    assert {s["category"] for s in compass["segments"]} == {
        "customer_facing",
        "process",
        "strategic",
    }
    # The lowest five carry their rank; the two strongest do not.
    assert segments["channel_navigation"]["priority_rank"] == 1
    assert segments["customer_journey"]["priority_rank"] is None


def test_the_iq_compass_carries_the_books_level_for_each_segment(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    confirmed_idea(client, use_ai, {"organizational_agility": 3})
    iq = _dashboard(client)["iq"]
    compass = iq["compass"]

    assert compass["scale"] == "iq"
    assert (compass["minimum"], compass["maximum"]) == (1, 10)
    assert [s["key"] for s in compass["segments"]] == KEYS
    # The legend is the book's three levels, lowest first (spec 3.1).
    assert [(lvl["name"], lvl["min"], lvl["max"], lvl["order"]) for lvl in compass["levels"]] == [
        ("Continuous Improvement", 1, 3, 1),
        ("Innovation", 4, 6, 2),
        ("Invention", 7, 10, 3),
    ]
    segments = _segments(compass)
    assert segments["organizational_agility"]["score"] == 3
    assert segments["organizational_agility"]["level"] == {
        "key": "continuous_improvement",
        "name": "Continuous Improvement",
        "order": 1,
    }
    assert segments["sustainable_future"]["level"]["name"] == "Innovation"
    assert segments["product_evolution"]["level"]["name"] == "Invention"
    # Category IQ: mean of its dimension scores x 10 (spec 3.6).
    assert [(c["key"], c["score"], c["maximum"]) for c in compass["categories"]] == [
        ("customer_facing", "74.0", "100.0"),
        ("process", "45.0", "100.0"),
        ("strategic", "72.0", "100.0"),
    ]
    # Priorities as the engine ranked them, with the level and the book's next steps.
    assert [(p["rank"], p["key"], p["score"]) for p in iq["priorities"]][:2] == [
        (1, "organizational_agility", 3),
        (2, "sustainable_future", 5),
    ]
    assert iq["priorities"][0]["level_name"] == "Continuous Improvement"
    assert (
        iq["priorities"][0]["next_steps"]
        == QUESTION_SET.dimension("organizational_agility").next_steps
    )
    assert iq["custom_weights"] is False


def test_only_confirmed_scores_are_ever_shown(client: TestClient, use_ai: UseAi) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)

    # A proposal that nobody confirmed is not on the dashboard.
    waiting = add_idea(client, title="Still under review")
    propose(client, use_ai, waiting)
    assert _dashboard(client)["ideas"] == []
    assert _dashboard(client)["iq"] is None
    assert client.get(DASHBOARD, params={"idea_id": waiting}).status_code == 404

    # Once confirmed it is. Scoring it again keeps showing the confirmed scores while the
    # new proposal is under review.
    idea_id, assessment_id = confirmed_idea(client, use_ai, title="Confirmed idea")
    again = propose(client, use_ai, idea_id)
    body = _dashboard(client)
    assert [i["idea_id"] for i in body["ideas"]] == [idea_id]
    assert body["iq"]["assessment_id"] == assessment_id
    assert body["iq"]["iq"] == "70.0"

    # Confirming the second assessment moves the dashboard on to it.
    confirm(client, idea_id, again, {"organizational_agility": 10})
    assert _dashboard(client)["iq"]["assessment_id"] == again
    assert _dashboard(client)["iq"]["iq"] == "74.2"  # 89 / 120 x 100


def test_the_selected_idea_is_the_one_asked_for(client: TestClient, use_ai: UseAi) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    first, _ = confirmed_idea(client, use_ai, title="First idea")
    second, _ = confirmed_idea(client, use_ai, {}, title="Second idea")

    body = _dashboard(client)
    # The most recently confirmed idea is first and selected.
    assert [i["title"] for i in body["ideas"]] == ["Second idea", "First idea"]
    assert body["iq"]["idea_id"] == second
    assert body["iq"]["iq"] == "69.2"  # the proposal unchanged: 83 / 120 x 100
    assert _dashboard(client, first)["iq"]["iq"] == "70.0"

    # An archived idea leaves the picker.
    assert client.post(f"{IDEAS}/{second}/archive", headers=csrf(client)).status_code == 200
    assert [i["idea_id"] for i in _dashboard(client)["ideas"]] == [first]
    assert client.get(DASHBOARD, params={"idea_id": second}).status_code == 404


def test_every_reader_sees_it_and_nobody_else_does(client: TestClient, use_ai: UseAi) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    finish_readiness(client, answers_190())
    idea_id, _ = confirmed_idea(client, use_ai)

    for role in (MembershipRole.MEMBER, MembershipRole.COMMITTEE, MembershipRole.INVESTOR):
        person, _ = member(role, org)
        as_user(client, person, org)
        body = _dashboard(client)
        assert body["readiness"]["total"] == 190, role
        assert body["iq"]["iq"] == "70.0", role

    # A consultant with live access reads the same final results.
    consultant = verified_user()
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=consultant.email,
        consultant_user_id=consultant.id,
        accepted_at=datetime.now(UTC),
    )
    as_user(client, consultant, org)
    assert _dashboard(client)["readiness"]["total"] == 190
    assert client.get(f"{DASHBOARD}/dimensions/customer_journey").status_code == 200
    assert client.get(f"{HISTORY}/readiness").status_code == 200
    assert client.get(f"{HISTORY}/ideas/{idea_id}").status_code == 200

    # Another organisation sees none of it and cannot select the idea.
    outsider, other = member(MembershipRole.OWNER)
    as_user(client, outsider, other)
    assert _dashboard(client) == {"readiness": None, "ideas": [], "iq": None}
    assert client.get(DASHBOARD, params={"idea_id": idea_id}).status_code == 404
    assert client.get(f"{HISTORY}/ideas/{idea_id}").status_code == 404
    assert client.get(f"{HISTORY}/readiness").json() == {"entries": []}
    detail = client.get(f"{DASHBOARD}/dimensions/customer_journey").json()
    assert (detail["readiness"], detail["iq"], detail["ideas"]) == (None, None, [])

    client.cookies.clear()
    assert client.get(DASHBOARD).status_code == 401


def test_a_result_on_an_unknown_question_set_version_is_left_out(
    client: TestClient, use_ai: UseAi, db: Session
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    old_readiness = finish_readiness(client)
    newer_readiness = finish_readiness(client, answers_190())
    old_idea, old_assessment = confirmed_idea(client, use_ai, title="Old method")
    idea_id, _ = confirmed_idea(client, use_ai, title="Current method")
    readiness_row = db.get(ReadinessAssessment, old_readiness)
    iq_row = db.get(IqAssessment, old_assessment)
    assert readiness_row is not None
    assert iq_row is not None
    readiness_row.question_set_version = 999
    iq_row.question_set_version = 999
    db.commit()

    body = _dashboard(client)
    assert body["readiness"]["assessment_id"] == newer_readiness
    assert [i["idea_id"] for i in body["ideas"]] == [idea_id]
    assert client.get(DASHBOARD, params={"idea_id": old_idea}).status_code == 404
    entries = client.get(f"{HISTORY}/readiness").json()["entries"]
    assert [e["assessment_id"] for e in entries] == [newer_readiness]
    assert entries[0]["compared_with"] is None  # never compared across versions (spec 9)


# Drill-down (P5.04)


def test_a_dimension_page_has_the_books_text_and_both_scores_apart(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    readiness_id = finish_readiness(client, answers_190())
    idea_id, assessment_id = confirmed_idea(
        client, use_ai, {"organizational_agility": 5}, title="Golden idea"
    )
    book = QUESTION_SET.dimension("organizational_agility")

    response = client.get(f"{DASHBOARD}/dimensions/organizational_agility")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert (detail["key"], detail["name"], detail["order"]) == (book.key, book.name, 7)
    assert detail["category"] == {"key": "process", "name": "Process Innovation", "order": 2}
    assert detail["description"] == book.description
    assert detail["sub_aspects"] == list(book.sub_aspects)
    assert detail["next_steps"] == book.next_steps  # the book's words, as written (spec 8)
    assert detail["previous"]["key"] == "operational_efficiency"
    assert detail["next"]["key"] == "collaborative_synergy"

    readiness = detail["readiness"]
    assert readiness["assessment_id"] == readiness_id
    assert (readiness["score"], readiness["maximum"]) == (15, 25)
    assert readiness["priority_rank"] == 5
    assert [q["text"] for q in readiness["questions"]] == [q.text for q in book.questions]
    assert [q["answer"] for q in readiness["questions"]] == [3, 3, 3, 3, 3]
    assert readiness["answer_scale"]["labels"] == {"1": "Strongly Disagree", "5": "Strongly Agree"}
    assert (readiness["target"], readiness["gap"]) == (None, None)
    assert [(h["score"], h["change"], h["direction"]) for h in readiness["history"]] == [
        (15, None, None)
    ]

    iq = detail["iq"]
    assert (iq["idea_id"], iq["assessment_id"], iq["idea_title"]) == (
        idea_id,
        assessment_id,
        "Golden idea",
    )
    assert (iq["score"], iq["maximum"], iq["proposed_score"], iq["changed"]) == (5, 10, 4, True)
    assert iq["level"]["name"] == "Innovation"
    assert iq["level"]["text"] == QUESTION_SET.iq_levels[1].text
    assert len(iq["rationale"]) == 2
    assert iq["priority_rank"] == 1
    assert [i["idea_id"] for i in detail["ideas"]] == [idea_id]

    # The first and last dimensions have one neighbour each; an unknown key is not found.
    assert client.get(f"{DASHBOARD}/dimensions/{KEYS[0]}").json()["previous"] is None
    assert client.get(f"{DASHBOARD}/dimensions/{KEYS[-1]}").json()["next"] is None
    assert client.get(f"{DASHBOARD}/dimensions/not_a_dimension").status_code == 404


def test_a_dimension_page_without_results_still_has_the_books_text(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    detail = client.get(f"{DASHBOARD}/dimensions/brand_magnetism").json()
    assert detail["next_steps"] == QUESTION_SET.dimension("brand_magnetism").next_steps
    assert (detail["readiness"], detail["iq"]) == (None, None)


# Targets and gaps on results (P5.06)


def _set_targets(client: TestClient, scale: str, targets: dict[str, Any]) -> None:
    response = client.put(f"{TARGETS}/{scale}", json={"targets": targets}, headers=csrf(client))
    assert response.status_code == 200, response.text


def test_gaps_are_target_minus_current_on_each_scale(client: TestClient, use_ai: UseAi) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    finish_readiness(client, answers_190())
    confirmed_idea(client, use_ai)
    # Readiness: customer_journey scores 20, channel_navigation and data_intelligence 15.
    _set_targets(
        client,
        "readiness",
        {"customer_journey": 20, "channel_navigation": 22, "data_intelligence": 10},
    )
    # IQ: organizational_agility is 5, product_evolution 9, sustainable_future 5.
    _set_targets(
        client,
        "iq",
        {"organizational_agility": 8, "product_evolution": 9, "sustainable_future": 3},
    )

    body = _dashboard(client)
    readiness = _segments(body["readiness"]["compass"])
    assert (readiness["customer_journey"]["target"], readiness["customer_journey"]["gap"]) == (
        20,
        0,
    )
    assert (readiness["channel_navigation"]["target"], readiness["channel_navigation"]["gap"]) == (
        22,
        7,
    )
    assert (readiness["data_intelligence"]["target"], readiness["data_intelligence"]["gap"]) == (
        10,
        -5,
    )
    assert (readiness["brand_magnetism"]["target"], readiness["brand_magnetism"]["gap"]) == (
        None,
        None,
    )
    iq = _segments(body["iq"]["compass"])
    assert (iq["organizational_agility"]["target"], iq["organizational_agility"]["gap"]) == (8, 3)
    assert (iq["product_evolution"]["target"], iq["product_evolution"]["gap"]) == (9, 0)
    assert (iq["sustainable_future"]["target"], iq["sustainable_future"]["gap"]) == (3, -2)
    # A readiness target never lands on the idea's compass, nor the other way round.
    assert iq["channel_navigation"]["target"] is None
    assert readiness["organizational_agility"]["target"] is None

    # The drill-down and both result pages show the same gap.
    detail = client.get(f"{DASHBOARD}/dimensions/organizational_agility").json()
    assert (detail["iq"]["target"], detail["iq"]["gap"]) == (8, 3)
    assert (detail["readiness"]["target"], detail["readiness"]["gap"]) == (None, None)
    result = client.get(
        f"/api/v1/readiness/assessments/{body['readiness']['assessment_id']}/result"
    ).json()
    assert _segments(result["compass"])["channel_navigation"]["gap"] == 7
    assessment = client.get(
        f"{IDEAS}/{body['iq']['idea_id']}/assessments/{body['iq']['assessment_id']}"
    ).json()
    assert _segments(assessment["compass"])["organizational_agility"]["gap"] == 3

    # Changing a target changes the gap; the score never moves.
    _set_targets(client, "iq", {"organizational_agility": 5})
    iq = _segments(_dashboard(client)["iq"]["compass"])
    assert (iq["organizational_agility"]["score"], iq["organizational_agility"]["gap"]) == (5, 0)
    assert iq["product_evolution"]["target"] is None
    assert _dashboard(client)["iq"]["iq"] == "70.0"


# History over time (P5.07)


def test_readiness_history_compares_each_result_with_the_one_before(
    client: TestClient,
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    first = finish_readiness(client, all_answers(3))  # 180: every dimension 15
    second = finish_readiness(client, answers_190())  # two dimensions rise to 20
    lower = all_answers(3)
    lower[QUESTION_SET.question_ids("customer_journey")[0]] = 1  # customer_journey 13
    third = finish_readiness(client, lower)  # 178
    _set_targets(client, "readiness", {"customer_journey": 20})

    response = client.get(f"{HISTORY}/readiness")
    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert [e["assessment_id"] for e in entries] == [third, second, first]  # newest first
    assert [e["total"] for e in entries] == [178, 190, 180]
    assert [e["band_name"] for e in entries] == ["Building Blocks"] * 3
    assert [e["compared_with"] for e in entries] == [second, first, None]
    assert [(e["total_change"], e["total_direction"]) for e in entries] == [
        (-12, "down"),
        (10, "up"),
        (None, None),
    ]

    def journey(entry: dict[str, Any]) -> dict[str, Any]:
        row: dict[str, Any] = next(d for d in entry["dimensions"] if d["key"] == KEYS[0])
        return row

    assert [
        (journey(e)["score"], journey(e)["change"], journey(e)["direction"]) for e in entries
    ] == [
        (13, -7, "down"),
        (20, 5, "up"),
        (15, None, None),
    ]
    last = next(d for d in entries[0]["dimensions"] if d["key"] == KEYS[-1])
    assert (last["change"], last["direction"]) == (0, "same")
    # Each entry is held against today's target.
    assert [(journey(e)["target"], journey(e)["gap"]) for e in entries] == [
        (20, 7),
        (20, 0),
        (20, 5),
    ]
    assert [d["key"] for d in entries[0]["dimensions"]] == KEYS

    # The drill-down shows the same trend for the dimension.
    detail = client.get(f"{DASHBOARD}/dimensions/customer_journey").json()
    assert [(h["score"], h["change"], h["direction"]) for h in detail["readiness"]["history"]] == [
        (13, -7, "down"),
        (20, 5, "up"),
        (15, None, None),
    ]
    # An earlier result still opens as it was.
    earlier = client.get(f"/api/v1/readiness/assessments/{first}/result").json()
    assert earlier["total"] == 180


def test_idea_history_compares_iq_value_for_money_and_dimensions(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    idea_id, first = confirmed_idea(client, use_ai, {})  # 83: IQ 69.2, 50,000 / 69.2
    second = propose(client, use_ai, idea_id)
    confirm(client, idea_id, second, {"organizational_agility": 5, "customer_journey": 7})  # 83

    third = propose(client, use_ai, idea_id)
    confirm(client, idea_id, third, {"organizational_agility": 5})  # 84: IQ 70.0

    response = client.get(f"{HISTORY}/ideas/{idea_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["idea_id"] == idea_id
    entries = body["entries"]
    assert [e["assessment_id"] for e in entries] == [third, second, first]
    assert [e["iq"] for e in entries] == ["70.0", "69.2", "69.2"]
    assert [e["compared_with"] for e in entries] == [second, first, None]
    assert [(e["iq_change"], e["iq_direction"]) for e in entries] == [
        ("0.8", "up"),
        ("0.0", "same"),
        (None, None),
    ]
    assert [e["vfm"]["per_point"] for e in entries] == ["714.29", "722.54", "722.54"]
    # A lower cost per innovation point: the number went down.
    assert [(e["vfm_change"], e["vfm_direction"]) for e in entries] == [
        ("-8.25", "down"),
        ("0.00", "same"),
        (None, None),
    ]

    def of(entry: dict[str, Any], key: str) -> tuple[int, int | None, str | None]:
        row = next(d for d in entry["dimensions"] if d["key"] == key)
        return row["score"], row["change"], row["direction"]

    assert of(entries[0], "customer_journey") == (8, 1, "up")
    assert of(entries[1], "customer_journey") == (7, -1, "down")
    assert of(entries[1], "organizational_agility") == (5, 1, "up")
    assert of(entries[2], "organizational_agility") == (
        GOLDEN_SCORES["organizational_agility"],
        None,
        None,
    )

    # The drill-down follows the selected idea's assessments.
    detail = client.get(
        f"{DASHBOARD}/dimensions/customer_journey", params={"idea_id": idea_id}
    ).json()
    assert [(h["score"], h["change"]) for h in detail["iq"]["history"]] == [
        (8, 1),
        (7, -1),
        (8, None),
    ]


def test_value_for_money_is_not_compared_across_currencies(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    idea_id, _ = confirmed_idea(client, use_ai)
    changed = client.patch(f"{IDEAS}/{idea_id}", json={"currency": "EUR"}, headers=csrf(client))
    assert changed.status_code == 200, changed.text
    confirm(client, idea_id, propose(client, use_ai, idea_id), {"organizational_agility": 6})

    entries = client.get(f"{HISTORY}/ideas/{idea_id}").json()["entries"]
    assert [e["vfm"]["currency"] for e in entries] == ["EUR", "USD"]
    assert (entries[0]["iq_change"], entries[0]["iq_direction"]) == ("0.8", "up")
    assert (entries[0]["vfm_change"], entries[0]["vfm_direction"]) == (None, None)


def test_an_idea_without_a_confirmed_assessment_has_an_empty_history(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    idea_id = add_idea(client)
    propose(client, use_ai, idea_id)
    body = client.get(f"{HISTORY}/ideas/{idea_id}").json()
    assert body["entries"] == []
