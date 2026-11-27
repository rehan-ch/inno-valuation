"""AI advice over HTTP (Phase 6): who may read and ask, what is stored and versioned, and
that nothing crosses from one organisation to another."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.client import AiUnavailableError
from app.ai.config import AiConfig, get_ai_config
from app.models import AiRun, AuditEvent, Interpretation, Organisation, Recommendation, User
from app.models.enums import AdviceSubject, AiRunStatus, AiTouchpoint, MembershipRole
from app.scoring.question_set import QUESTION_SET
from app.services import advice
from tests.ai.support import RecordedAiClient, fixture, recorded_replies
from tests.api.flows import (
    IDEAS,
    READINESS,
    add_idea,
    answers_190,
    as_user,
    confirmed_idea,
    finish_readiness,
    propose,
)
from tests.api.helpers import csrf, member
from tests.factories import ConsultantGrantFactory, verified_user

UseAi = Callable[..., RecordedAiClient]

PARTS = {
    "interpretation": "interpret_results",
    "gap_actions": "bridge_gaps",
    "recommendations": "recommendations",
    "consultation": "consultation_nudge",
}
NEXT_STEPS = {d.key: d.next_steps for d in QUESTION_SET.dimensions}


def _typical(*parts: str) -> list[Any]:
    """The recorded typical answers (a readiness result of 190) for ``parts``, in order."""
    return [
        reply
        for part in (parts or PARTS)
        for reply in recorded_replies(fixture(PARTS[part], "typical"))
    ]


def _readiness(client: TestClient) -> tuple[User, Organisation, str]:
    """An owner with a final readiness result of 190 and one target, as in the typical
    recorded case. Returns the advice URL."""
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    assessment_id = finish_readiness(client, answers_190())
    saved = client.put(
        "/api/v1/targets/readiness",
        json={"targets": {"customer_journey": 23}},
        headers=csrf(client),
    )
    assert saved.status_code == 200, saved.text
    return owner, org, f"{READINESS}/assessments/{assessment_id}/advice"


def _ask(client: TestClient, url: str, **body: Any) -> dict[str, Any]:
    response = client.post(url, json=body, headers=csrf(client))
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


def _get(client: TestClient, url: str) -> dict[str, Any]:
    response = client.get(url)
    assert response.status_code == 200, response.text
    found: dict[str, Any] = response.json()
    return found


def _statuses(body: dict[str, Any]) -> list[str]:
    return [body[part]["status"] for part in PARTS]


def _runs(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(AiRun).where(AiRun.touchpoint.in_(advice.PARTS)))
        or 0
    )


def test_nothing_is_asked_until_someone_asks(client: TestClient, db: Session) -> None:
    _, _, url = _readiness(client)
    body = _get(client, url)
    assert _statuses(body) == ["none"] * 4
    assert body["subject"] == "readiness_result"
    assert body["can_request"] is True
    assert body["interpretation"]["summary"] == []
    assert _runs(db) == 0


def test_full_advice_on_a_readiness_result(client: TestClient, db: Session, use_ai: UseAi) -> None:
    _, org, url = _readiness(client)
    ai = use_ai(*_typical())
    body = _ask(client, url)
    assert _statuses(body) == ["ready"] * 4
    assert len(ai.requests) == 4

    # The interpretation: every dimension once, words only.
    assert [d["key"] for d in body["interpretation"]["dimensions"]] == list(
        QUESTION_SET.dimension_keys
    )
    text = " ".join(
        [*body["interpretation"]["summary"]]
        + [
            s
            for d in body["interpretation"]["dimensions"]
            for s in (d["meaning"], *d["strengths"], *d["gaps"])
        ]
    )
    assert not any(character.isdigit() for character in text)

    # Recommendations: the engine's five priorities in order, Amy's text kept apart.
    items = body["recommendations"]["items"]
    assert [i["rank"] for i in items] == [1, 2, 3, 4, 5]
    assert all(i["fixed_text"] == NEXT_STEPS[i["key"]] for i in items)
    assert all(NEXT_STEPS[i["key"]] not in " ".join(i["initiatives"]) for i in items)

    # Gap actions: the priorities, then the dimension with a target above its score.
    gap_keys = [d["key"] for d in body["gap_actions"]["dimensions"]]
    assert gap_keys == [*(i["key"] for i in items), "customer_journey"]
    assert all(3 <= len(d["actions"]) <= 5 for d in body["gap_actions"]["dimensions"])

    # The consultation suggestion names the dimensions behind it.
    assert body["consultation"]["suggest"] is True
    assert body["consultation"]["message"]
    assert {r["key"] for r in body["consultation"]["reasons"]} <= set(gap_keys)

    # Both tables link every row to the run that produced it.
    interpretation = db.scalars(select(Interpretation)).one()
    rows = db.scalars(select(Recommendation)).all()
    assert len(rows) == 5
    run_ids = {interpretation.ai_run_id, *(row.ai_run_id for row in rows)}
    runs = db.scalars(select(AiRun).where(AiRun.id.in_(run_ids))).all()
    assert {run.touchpoint for run in runs} == {
        AiTouchpoint.INTERPRET_RESULTS,
        AiTouchpoint.RECOMMENDATIONS,
    }
    assert all(run.status is AiRunStatus.SUCCEEDED for run in runs)
    assert interpretation.organisation_id == org.id
    assert interpretation.subject_type is AdviceSubject.READINESS_RESULT
    assert (interpretation.version, {row.version for row in rows}) == (1, {1})

    # One event in the activity log, with no text from the result.
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "advice.requested")).one()
    assert event.details is not None
    assert event.details["parts"] == list(PARTS.values())
    assert event.details["rerun"] is False


def test_asking_twice_starts_nothing_new_and_reading_twice_stores_once(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    _, _, url = _readiness(client)
    use_ai(*_typical())
    _ask(client, url)
    again = _ask(client, url)  # would fail the recorded client if it called the AI
    assert _statuses(again) == ["ready"] * 4
    _get(client, url)
    assert _runs(db) == 4
    assert db.scalar(select(func.count()).select_from(Interpretation)) == 1
    assert db.scalar(select(func.count()).select_from(Recommendation)) == 5


def test_asking_again_keeps_the_earlier_version(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    _, _, url = _readiness(client)
    use_ai(*_typical(), *_typical("recommendations"))
    first = _ask(client, url)
    second = _ask(client, url, parts=["recommendations"], regenerate=True)
    assert first["recommendations"]["version"] == 1
    assert second["recommendations"]["version"] == 2
    assert second["interpretation"]["version"] == 1  # the other parts are left alone
    assert _runs(db) == 5
    versions = db.scalars(select(Recommendation.version).order_by(Recommendation.version)).all()
    assert versions == [1] * 5 + [2] * 5
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == "advice.requested")
        .order_by(AuditEvent.created_at, AuditEvent.id)
    ).all()
    assert [e.details["rerun"] for e in events if e.details] == [False, True]


def test_a_failed_refresh_keeps_showing_the_earlier_answer(
    client: TestClient, use_ai: UseAi
) -> None:
    _, _, url = _readiness(client)
    use_ai(*_typical("gap_actions"), AiUnavailableError("The AI service did not answer in time."))
    first = _ask(client, url, parts=["gap_actions"])
    second = _ask(client, url, parts=["gap_actions"], regenerate=True)
    assert second["gap_actions"]["status"] == "failed"
    assert second["gap_actions"]["dimensions"] == first["gap_actions"]["dimensions"]
    # Asking without "regenerate" tries a failed part again.
    use_ai(*_typical("gap_actions"))
    assert _ask(client, url, parts=["gap_actions"])["gap_actions"]["status"] == "ready"


def test_advice_is_outdated_once_a_target_changes(client: TestClient, use_ai: UseAi) -> None:
    _, _, url = _readiness(client)
    use_ai(*_typical())
    assert not any(_ask(client, url)[part]["outdated"] for part in PARTS)
    changed = client.put(
        "/api/v1/targets/readiness",
        json={"targets": {"customer_journey": 25}},
        headers=csrf(client),
    )
    assert changed.status_code == 200
    body = _get(client, url)
    # The parts that were told about the target would be asked differently today.
    assert {part: body[part]["outdated"] for part in PARTS} == {
        "interpretation": False,
        "gap_actions": True,
        "recommendations": False,
        "consultation": True,
    }
    assert _statuses(body) == ["ready"] * 4


def test_advice_on_an_idea(client: TestClient, db: Session, use_ai: UseAi) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    idea_id, assessment_id = confirmed_idea(client, use_ai)
    url = f"{IDEAS}/{idea_id}/assessments/{assessment_id}/advice"
    use_ai(
        *[
            reply
            for key in PARTS.values()
            for reply in recorded_replies(fixture(key, "adversarial"))
        ]
    )
    body = _ask(client, url)
    assert body["subject"] == "iq_assessment"
    assert _statuses(body) == ["ready"] * 4
    assert [i["key"] for i in body["recommendations"]["items"]] == [
        "organizational_agility",
        "sustainable_future",
        "channel_navigation",
        "operational_efficiency",
        "brand_magnetism",
    ]
    assert db.scalars(select(Interpretation)).one().subject_type is AdviceSubject.IQ_ASSESSMENT
    # The readiness side has none of it: the two scores never share advice.
    readiness_id = finish_readiness(client)
    other = _get(client, f"{READINESS}/assessments/{readiness_id}/advice")
    assert _statuses(other) == ["none"] * 4


def test_no_advice_before_the_result_is_final_or_confirmed(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    started = client.post(f"{READINESS}/assessments", headers=csrf(client)).json()["id"]
    url = f"{READINESS}/assessments/{started}/advice"
    assert client.get(url).status_code == 404
    assert client.post(url, json={}, headers=csrf(client)).status_code == 404

    idea_id = add_idea(client)
    assessment_id = propose(client, use_ai, idea_id)
    url = f"{IDEAS}/{idea_id}/assessments/{assessment_id}/advice"
    assert client.get(url).status_code == 404
    assert client.post(url, json={}, headers=csrf(client)).status_code == 404


@pytest.mark.parametrize(
    ("role", "may_ask"),
    [
        (MembershipRole.ADMIN, True),
        (MembershipRole.MEMBER, True),
        (MembershipRole.COMMITTEE, True),
        (MembershipRole.INVESTOR, False),
    ],
)
def test_who_may_ask(
    client: TestClient, db: Session, use_ai: UseAi, role: MembershipRole, may_ask: bool
) -> None:
    _, org, url = _readiness(client)
    person, _ = member(role, org)
    as_user(client, person, org)
    assert _get(client, url)["can_request"] is may_ask
    use_ai(*_typical("interpretation"))
    asked = client.post(url, json={"parts": ["interpretation"]}, headers=csrf(client))
    assert asked.status_code == (200 if may_ask else 403)
    assert _runs(db) == (1 if may_ask else 0)


def test_a_consultant_reads_advice_and_never_asks(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    _, org, url = _readiness(client)
    use_ai(*_typical())
    _ask(client, url)
    consultant = verified_user()
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=consultant.email,
        consultant_user_id=consultant.id,
        accepted_at=datetime.now(UTC),
    )
    as_user(client, consultant, org)
    body = _get(client, url)
    assert _statuses(body) == ["ready"] * 4
    assert body["can_request"] is False
    refused = client.post(url, json={"regenerate": True}, headers=csrf(client))
    assert refused.status_code == 403
    assert _runs(db) == 4


def test_another_organisation_sees_and_asks_nothing(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    _, _, url = _readiness(client)
    use_ai(*_typical())
    _ask(client, url)
    idea_owner, idea_org = member(MembershipRole.OWNER)
    as_user(client, idea_owner, idea_org)
    idea_id, assessment_id = confirmed_idea(client, use_ai)
    idea_url = f"{IDEAS}/{idea_id}/assessments/{assessment_id}/advice"

    outsider, other_org = member(MembershipRole.OWNER)
    as_user(client, outsider, other_org)
    for hidden in (url, idea_url):
        assert client.get(hidden).status_code == 404
        assert client.post(hidden, json={}, headers=csrf(client)).status_code == 404
    assert _runs(db) == 4


def test_usage_figures_are_for_platform_admins_only(client: TestClient, use_ai: UseAi) -> None:
    _, org, url = _readiness(client)
    use_ai(*_typical())
    body = _ask(client, url)
    assert all(body[part]["usage"] is None for part in PARTS)
    staff, _ = member(MembershipRole.MEMBER, org, is_platform_admin=True)
    as_user(client, staff, org)
    usage = _get(client, url)["interpretation"]["usage"]
    assert usage == {
        "model": "claude-sonnet-5-5",
        "input_tokens": 600,
        "output_tokens": 150,
        "cost_usd": "0.0027",
    }


def test_without_a_key_the_stand_in_answers_with_marked_samples(client: TestClient) -> None:
    _, _, url = _readiness(client)
    body = _ask(client, url)
    assert _statuses(body) == ["ready"] * 4
    assert all(body[part]["sample"] for part in PARTS)
    assert "sample text" in body["interpretation"]["summary"][0]
    # A sample never suggests a consultation, and still keeps Amy's text unchanged.
    assert body["consultation"]["suggest"] is False
    assert all(i["fixed_text"] == NEXT_STEPS[i["key"]] for i in body["recommendations"]["items"])


def test_samples_are_not_shown_once_the_ai_is_connected(client: TestClient, use_ai: UseAi) -> None:
    _, _, url = _readiness(client)
    _ask(client, url)  # offline samples
    use_ai()  # a connected client, never called by a read
    assert _statuses(_get(client, url)) == ["none"] * 4


def test_a_part_switched_off_in_the_settings_is_never_asked(
    client: TestClient, db: Session, use_ai: UseAi, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = get_ai_config()
    nudge = config.touchpoints[AiTouchpoint.CONSULTATION_NUDGE].model_copy(
        update={"enabled": False}
    )
    off = AiConfig(
        models=config.models,
        touchpoints={**config.touchpoints, AiTouchpoint.CONSULTATION_NUDGE: nudge},
    )
    monkeypatch.setattr(advice, "get_ai_config", lambda: off)
    _, _, url = _readiness(client)
    use_ai(*_typical("interpretation", "gap_actions", "recommendations"))
    body = _ask(client, url)
    assert _statuses(body) == ["ready", "ready", "ready", "off"]
    assert _runs(db) == 3


def test_the_daily_limit(
    client: TestClient, db: Session, use_ai: UseAi, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(advice, "DAILY_LIMIT", 4)
    _, _, url = _readiness(client)
    use_ai(*_typical())
    _ask(client, url)
    refused = client.post(url, json={"regenerate": True}, headers=csrf(client))
    assert refused.status_code == 429
    assert _runs(db) == 4


def test_asking_needs_the_csrf_header_and_a_known_part(client: TestClient, db: Session) -> None:
    _, _, url = _readiness(client)
    assert client.post(url, json={}).status_code == 403
    bad = client.post(url, json={"parts": ["total"]}, headers=csrf(client))
    assert bad.status_code == 422
    extra = client.post(url, json={"score": 300}, headers=csrf(client))
    assert extra.status_code == 422
    assert _runs(db) == 0


def test_the_activity_log_says_what_was_asked_in_plain_words(
    client: TestClient, use_ai: UseAi
) -> None:
    _, _, url = _readiness(client)
    use_ai(*_typical(), *_typical("consultation"))
    _ask(client, url)
    _ask(client, url, parts=["consultation"], regenerate=True)
    events = [
        e for e in client.get("/api/v1/audit").json()["events"] if e["action"] == "advice.requested"
    ]
    assert [(e["action_label"], e["detail"]) for e in events] == [
        (
            "AI advice requested",
            "For a readiness result: consultation suggestion. Asked again.",
        ),
        (
            "AI advice requested",
            "For a readiness result: what the result means, actions to close the gaps, "
            "recommendations, consultation suggestion.",
        ),
    ]
    assert all(e["ai_model"] and e["question_set_version"] == 1 for e in events)
