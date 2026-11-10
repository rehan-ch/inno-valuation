"""Whole flows over HTTP for tests that need a finished result to start from: a final
readiness result, and an idea with a confirmed IQ assessment. No live AI call anywhere."""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.models import Organisation, User
from app.scoring.question_set import QUESTION_SET
from tests.ai.support import RecordedAiClient, fixture, recorded_replies
from tests.api.helpers import csrf, signed_in

UseAi = Callable[..., RecordedAiClient]

READINESS = "/api/v1/readiness"
IDEAS = "/api/v1/ideas"
QUESTION_IDS = QUESTION_SET.all_question_ids()
KEYS = list(QUESTION_SET.dimension_keys)
# The recorded proposal of P4.09: 12 scores that add up to 83.
GOLDEN = fixture("propose_iq_scores", "typical")
GOLDEN_SCORES: dict[str, int] = {
    s["dimension_key"]: s["score"] for s in GOLDEN["replies"][0]["output"]["scores"]
}


def as_user(client: TestClient, user: User, org: Organisation) -> None:
    client.cookies.clear()
    signed_in(client, user, org)


def all_answers(value: int) -> dict[str, int]:
    return dict.fromkeys(QUESTION_IDS, value)


def answers_190() -> dict[str, int]:
    """Golden example (P3.07): the first two dimensions score 20, the other ten 15."""
    answers = all_answers(3)
    for question_id in QUESTION_IDS[:10]:
        answers[question_id] = 4
    return answers


def finish_readiness(client: TestClient, answers: dict[str, int] | None = None) -> str:
    """The signed-in owner or admin runs a whole assessment alone: answers, submits, agrees
    ``answers`` (every answer 3 by default) and finalises. Returns the assessment id."""
    agreed = answers or all_answers(3)
    started = client.post(f"{READINESS}/assessments", headers=csrf(client))
    assert started.status_code == 201, started.text
    assessment_id: str = started.json()["id"]
    base = f"{READINESS}/assessments/{assessment_id}"
    for method, path, body in (
        ("PATCH", "my-answers", {"answers": agreed}),
        ("POST", "my-answers/submit", None),
        ("POST", "consensus/begin", None),
        ("PATCH", "consensus", {"answers": agreed, "notes": {}}),
        ("POST", "finalise", None),
    ):
        response = client.request(method, f"{base}/{path}", json=body, headers=csrf(client))
        assert response.status_code == 200, response.text
    return assessment_id


def add_idea(client: TestClient, **changes: Any) -> str:
    body: dict[str, Any] = {**GOLDEN["idea"], "investment": "50000.00"}
    body.update(changes)
    created = client.post(IDEAS, json=body, headers=csrf(client))
    assert created.status_code == 201, created.text
    idea_id: str = created.json()["id"]
    return idea_id


def propose(client: TestClient, use_ai: UseAi, idea_id: str) -> str:
    """Send the idea for scoring; the recorded proposal comes back ready."""
    use_ai(*recorded_replies(GOLDEN))
    proposed = client.post(f"{IDEAS}/{idea_id}/assessments", headers=csrf(client))
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["proposal_status"] == "ready"
    assessment_id: str = proposed.json()["id"]
    return assessment_id


def confirm(
    client: TestClient,
    idea_id: str,
    assessment_id: str,
    scores: dict[str, int] | None = None,
    notes: dict[str, str] | None = None,
) -> dict[str, Any]:
    base = f"{IDEAS}/{idea_id}/assessments/{assessment_id}"
    if scores or notes:
        reviewed = client.patch(
            f"{base}/review",
            json={"scores": scores or {}, "notes": notes or {}},
            headers=csrf(client),
        )
        assert reviewed.status_code == 200, reviewed.text
    confirmed = client.post(f"{base}/confirm", headers=csrf(client))
    assert confirmed.status_code == 200, confirmed.text
    body: dict[str, Any] = confirmed.json()
    return body


def confirmed_idea(
    client: TestClient,
    use_ai: UseAi,
    scores: dict[str, int] | None = None,
    **idea: Any,
) -> tuple[str, str]:
    """The signed-in person adds the golden idea, gets the recorded proposal (scores adding
    up to 83) and confirms it with ``scores`` changed. By default Organizational Agility
    goes from 4 to 5, the golden flow: IQ 70.0, Value for Money 714.29 for 50,000.
    Returns (idea id, assessment id)."""
    idea_id = add_idea(client, **idea)
    assessment_id = propose(client, use_ai, idea_id)
    confirm(
        client,
        idea_id,
        assessment_id,
        {"organizational_agility": 5} if scores is None else scores,
    )
    return idea_id, assessment_id
