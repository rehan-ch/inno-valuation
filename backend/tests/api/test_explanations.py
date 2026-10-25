""" "What does this mean?" over HTTP (AI touchpoint 1): saved per organisation and question,
waited for by polling, never shown to another organisation."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.client import AiUnavailableError
from app.models import AiRun, Organisation, User
from app.models.enums import AiRunStatus, MembershipRole, OrganisationStatus
from app.scoring.question_set import QUESTION_SET
from app.services import explanations
from tests.ai.support import RecordedAiClient, reply
from tests.api.helpers import csrf, member, signed_in
from tests.factories import AiRunFactory, ConsultantGrantFactory, verified_user

UseAi = Callable[..., RecordedAiClient]

BASE = "/api/v1/readiness/questions"
QUESTION = "customer_journey_2"

GOOD = {
    "dimension_key": "customer_journey",
    "explanation": [
        "This question asks whether customer feedback shapes their experience.",
        "It should happen regularly, not once.",
    ],
    "example": "A grocer changes its shelf signs after reading weekly reviews.",
}


def _as(client: TestClient, user: User, org: Organisation) -> None:
    client.cookies.clear()
    signed_in(client, user, org)


def _ask(client: TestClient, question: str = QUESTION, **params: Any) -> httpx2.Response:
    response: httpx2.Response = client.post(
        f"{BASE}/{question}/explanation", params=params, headers=csrf(client)
    )
    return response


def _poll(client: TestClient, question: str = QUESTION, **params: Any) -> httpx2.Response:
    response: httpx2.Response = client.get(f"{BASE}/{question}/explanation", params=params)
    return response


def _runs(db: Session, org: Organisation) -> int:
    return int(
        db.scalar(select(func.count()).select_from(AiRun).where(AiRun.organisation_id == org.id))
        or 0
    )


def test_a_member_asks_and_gets_a_plain_explanation(client: TestClient, use_ai: UseAi) -> None:
    use_ai(reply(GOOD))
    person, org = member(MembershipRole.MEMBER)
    _as(client, person, org)
    body = _ask(client).json()
    assert body == {
        "question_id": QUESTION,
        "question_set_version": QUESTION_SET.version,
        "dimension_key": "customer_journey",
        "dimension_name": "Customer Journey",
        "status": "ready",
        "explanation": GOOD["explanation"],
        "example": GOOD["example"],
        "sample": False,
        "created_at": body["created_at"],
    }
    assert _poll(client).json() == body


def test_the_explanation_is_saved_for_the_next_person(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    ai = use_ai(reply(GOOD))
    first, org = member(MembershipRole.MEMBER)
    second, _ = member(MembershipRole.COMMITTEE, org)
    _as(client, first, org)
    asked = _ask(client).json()
    _as(client, second, org)
    assert _ask(client).json() == asked
    assert len(ai.requests) == 1
    assert _runs(db, org) == 1


def test_each_organisation_gets_its_own(client: TestClient, db: Session, use_ai: UseAi) -> None:
    ai = use_ai(reply(GOOD), reply(GOOD))
    one, org_one = member(MembershipRole.OWNER)
    two, org_two = member(MembershipRole.OWNER)
    _as(client, one, org_one)
    _ask(client)
    _as(client, two, org_two)
    assert _poll(client).status_code == 404  # nothing leaks across organisations
    _ask(client)
    assert len(ai.requests) == 2
    assert (_runs(db, org_one), _runs(db, org_two)) == (1, 1)


def test_changed_company_details_ask_again(client: TestClient, db: Session, use_ai: UseAi) -> None:
    ai = use_ai(reply(GOOD), reply(GOOD))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    _ask(client)
    org.industry = "Logistics"
    db.flush()
    _ask(client)
    assert len(ai.requests) == 2
    assert "Industry: Logistics" in ai.requests[1].user


def test_a_failed_explanation_can_be_asked_again(client: TestClient, use_ai: UseAi) -> None:
    use_ai(AiUnavailableError("The AI service did not answer in time."), reply(GOOD))
    person, org = member(MembershipRole.MEMBER)
    _as(client, person, org)
    failed = _ask(client).json()
    assert failed["status"] == "failed"
    assert failed["explanation"] is None
    assert _poll(client).json()["status"] == "failed"
    assert _ask(client).json()["status"] == "ready"


def test_a_waiting_run_is_shared_and_a_stale_one_replaced(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    person, org = member(MembershipRole.MEMBER)
    _as(client, person, org)
    # Ask once with the offline stand-in, so the waiting run carries the real prompts.
    asked = db.get(AiRun, _first_run_id(client, db, org))
    assert asked is not None
    asked.status = AiRunStatus.QUEUED
    asked.response_json = None
    db.flush()
    ai = use_ai(reply(GOOD))
    assert _ask(client).json()["status"] == "pending"  # the same run, still waiting
    assert ai.requests == []

    asked.created_at = datetime.now(UTC) - explanations.STALE_AFTER - timedelta(seconds=1)
    db.flush()
    assert _ask(client).json()["status"] == "ready"
    assert asked.status is AiRunStatus.FAILED
    assert asked.error == "The run did not finish in time."


def _first_run_id(client: TestClient, db: Session, org: Organisation) -> Any:
    _ask(client)
    return db.scalar(select(AiRun.id).where(AiRun.organisation_id == org.id))


def test_sample_text_is_marked_and_replaced_once_the_ai_is_connected(
    client: TestClient, use_ai: UseAi
) -> None:
    person, org = member(MembershipRole.MEMBER)
    _as(client, person, org)
    offline = _ask(client).json()  # no key in tests: the offline stand-in answers
    assert offline["status"] == "ready"
    assert offline["sample"] is True
    ai = use_ai(reply(GOOD))
    live = _ask(client).json()
    assert live["sample"] is False
    assert live["explanation"] == GOOD["explanation"]
    assert len(ai.requests) == 1


def test_the_daily_limit_says_when_to_try_again(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    person, org = member(MembershipRole.MEMBER)
    monkeypatch.setattr(explanations, "DAILY_LIMIT", 2)
    AiRunFactory.create_batch(2, organisation=org, status=AiRunStatus.FAILED)
    _as(client, person, org)
    refused = _ask(client)
    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "too_many_requests"
    assert "Try again in about 24 hours" in refused.json()["error"]["message"]


@pytest.mark.parametrize(
    ("question", "params"),
    [("not_a_question", {}), (QUESTION, {"version": 99}), ("x" * 101, {})],
)
def test_unknown_questions_are_not_found(
    client: TestClient, question: str, params: dict[str, Any]
) -> None:
    person, org = member(MembershipRole.MEMBER)
    _as(client, person, org)
    assert _ask(client, question, **params).status_code in {404, 422}
    assert _poll(client, question, **params).status_code in {404, 422}


def test_nobody_asked_yet_is_not_found(client: TestClient) -> None:
    person, org = member(MembershipRole.MEMBER)
    _as(client, person, org)
    assert _poll(client).status_code == 404


def test_watchers_read_but_do_not_start_ai_runs(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    use_ai(reply(GOOD))
    owner, org = member(MembershipRole.OWNER)
    investor, _ = member(MembershipRole.INVESTOR, org)
    amy = verified_user(email="amy@example.com")
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=amy.email,
        consultant_user_id=amy.id,
        accepted_at=datetime.now(UTC),
    )
    for watcher in (investor, amy):
        _as(client, watcher, org)
        assert _ask(client).status_code == 403
    _as(client, owner, org)
    _ask(client)
    for watcher in (investor, amy):
        _as(client, watcher, org)
        assert _poll(client).json()["status"] == "ready"
    assert _runs(db, org) == 1


def test_an_archived_organisation_starts_no_ai_runs(client: TestClient, db: Session) -> None:
    person, org = member(MembershipRole.OWNER)
    _as(client, person, org)  # the session has the organisation open when it is archived
    org.status = OrganisationStatus.ARCHIVED
    db.flush()
    refused = _ask(client)
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "organisation_archived"
    assert _runs(db, org) == 0


def test_signed_out_is_refused(client: TestClient) -> None:
    assert client.post(f"{BASE}/{QUESTION}/explanation").status_code == 401
    assert client.get(f"{BASE}/{QUESTION}/explanation").status_code == 401


def test_the_response_never_shows_prompts_or_use(client: TestClient, use_ai: UseAi) -> None:
    use_ai(reply(GOOD))
    person, org = member(MembershipRole.MEMBER)
    _as(client, person, org)
    body = _ask(client).json()
    for hidden in ("prompt", "model", "tokens", "cost", "raw", "error"):
        assert not [key for key in body if hidden in key]
