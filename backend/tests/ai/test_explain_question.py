"""Touchpoint 1 against its recorded cases: typical, sparse, adversarial, and the retry.

Each case asks through the service as a member, so the prompt is built from the case's
organisation, the run goes through the (eager) task, and the recorded replies answer.
"""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.core.permissions import OrgContext, OrgRole
from app.models.enums import AiRunStatus
from app.scoring.question_set import QUESTION_SET
from app.services import explanations
from tests.ai.support import RecordedAiClient, fixture, fixture_cases, recorded_replies
from tests.factories import OrganisationFactory, verified_user

UseAi = Callable[..., RecordedAiClient]

CASES = fixture_cases("explain_question")


def test_the_required_cases_are_recorded() -> None:
    assert {"typical", "sparse", "adversarial"} <= set(CASES)


@pytest.mark.parametrize("case", CASES)
def test_recorded_case(db: Session, use_ai: UseAi, case: str) -> None:
    data = fixture("explain_question", case)
    ai = use_ai(*recorded_replies(data))
    org = OrganisationFactory.create(**data["organisation"])
    ctx = OrgContext(organisation=org, user=verified_user(), role=OrgRole.MEMBER)

    run = explanations.request(db, ctx, QUESTION_SET.version, data["question_id"])

    expect = data["expect"]
    assert run.status.value == expect["status"]
    assert run.attempts == expect["attempts"]
    assert len(ai.requests) == expect["attempts"]
    assert run.provider_request_ids == [r["request_id"] for r in data["replies"]]
    dimension = QUESTION_SET.dimension_of_question(data["question_id"])
    if run.status is AiRunStatus.SUCCEEDED:
        assert run.response_json is not None
        assert run.response_json["dimension_key"] == dimension.key
        assert 2 <= len(run.response_json["explanation"]) <= 4
    else:
        assert run.response_json is None
        assert run.error is not None
        assert expect["error_contains"] in run.error
    # Whatever the company details say, they reach the model as escaped data only.
    user_prompt = ai.requests[0].user
    assert user_prompt.count("<data") == user_prompt.count("</data>") <= 1
    assert "Ignore all previous instructions" not in ai.requests[0].system


def test_an_injected_score_never_reaches_the_stored_answer(db: Session, use_ai: UseAi) -> None:
    data = fixture("explain_question", "adversarial_obeyed")
    use_ai(*recorded_replies(data))
    org = OrganisationFactory.create(**data["organisation"])
    ctx = OrgContext(organisation=org, user=verified_user(), role=OrgRole.MEMBER)
    run = explanations.request(db, ctx, QUESTION_SET.version, data["question_id"])
    assert run.status is AiRunStatus.FAILED
    assert run.response_json is None
    assert explanations.latest(db, ctx, QUESTION_SET.version, data["question_id"]) == run
