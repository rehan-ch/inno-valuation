"""The shared runner: one answer, one retry with the reason, then fail and keep the raw
answer. Every attempt's tokens, cost and request id land on the run."""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.ai import runner
from app.ai.client import OFFLINE_MODEL, AiRequestError, AiUnavailableError
from app.ai.touchpoints import explain_question
from app.models import AiRun
from app.models.enums import AiRunStatus
from tests.ai.support import RecordedAiClient, reply
from tests.factories import AiRunFactory

UseAi = Callable[..., RecordedAiClient]

GOOD = {
    "dimension_key": "customer_journey",
    "explanation": [
        "This question asks how well you know your customers.",
        "It covers every step they take with you.",
    ],
    "example": "A shop maps each step from first visit to repeat purchase.",
}


def _run(db: Session) -> AiRun:
    run = AiRunFactory.create(user_prompt="the user prompt")
    runner.execute(db, run, explain_question.spec_for(run))
    return run


def test_a_good_answer_is_stored_with_its_use(db: Session, use_ai: UseAi) -> None:
    ai = use_ai(reply(GOOD, input_tokens=612, output_tokens=148, request_id="req_1"))
    run = _run(db)
    assert run.status is AiRunStatus.SUCCEEDED
    assert run.response_json == GOOD
    assert run.response_model == "claude-sonnet-5-5"
    assert (run.attempts, run.input_tokens, run.output_tokens) == (1, 612, 148)
    assert run.cost_micro_usd == 2704  # $2 and $10 per million tokens
    assert run.provider_request_ids == ["req_1"]
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.error is None
    [request] = ai.requests
    assert request.run_id == run.id
    assert (request.model, request.effort) == ("claude-sonnet-5-5", "low")
    assert request.system == run.system_prompt
    assert request.user == "the user prompt"
    # Generation is held to the question's own dimension.
    assert request.output_schema["properties"]["dimension_key"]["enum"] == ["customer_journey"]


def test_a_rejected_answer_is_retried_once_with_the_reason(db: Session, use_ai: UseAi) -> None:
    ai = use_ai(reply(text="not json", request_id="req_1"), reply(GOOD, request_id="req_2"))
    run = _run(db)
    assert run.status is AiRunStatus.SUCCEEDED
    assert run.attempts == 2
    assert (run.input_tokens, run.output_tokens) == (1200, 300)  # both attempts count
    assert run.provider_request_ids == ["req_1", "req_2"]
    first, second = ai.requests
    assert first.user == "the user prompt"
    assert second.user.startswith("the user prompt\n\nYour previous answer was rejected: ")
    assert "not valid JSON" in second.user


def test_two_rejected_answers_fail_the_run_and_keep_the_raw_answer(
    db: Session, use_ai: UseAi
) -> None:
    wrong_dimension = {**GOOD, "dimension_key": "brand_magnetism"}
    use_ai(reply(wrong_dimension), reply(text='{"dimension_key": "customer_journey"}'))
    run = _run(db)
    assert run.status is AiRunStatus.FAILED
    assert run.attempts == 2
    assert run.response_json is None
    assert run.response_raw == '{"dimension_key": "customer_journey"}'
    assert run.error is not None
    assert run.error.startswith("The answer failed the check 2 times.")
    assert "explanation: Field required" in run.error


def test_the_wrong_dimension_is_rejected_by_the_check(db: Session, use_ai: UseAi) -> None:
    ai = use_ai(reply({**GOOD, "dimension_key": "brand_magnetism"}), reply(GOOD))
    run = _run(db)
    assert run.status is AiRunStatus.SUCCEEDED
    assert "must be 'customer_journey'" in ai.requests[1].user


def test_a_cut_off_answer_says_so_in_the_retry(db: Session, use_ai: UseAi) -> None:
    ai = use_ai(reply(text='{"dimension_key": "cust', stop_reason="max_tokens"), reply(GOOD))
    _run(db)
    assert "cut off at the token limit" in ai.requests[1].user


@pytest.mark.parametrize(
    "error",
    [AiUnavailableError("The AI service did not answer in time."), AiRequestError("HTTP 400")],
)
def test_a_failed_call_fails_the_run_at_once(db: Session, use_ai: UseAi, error: Exception) -> None:
    ai = use_ai(error)
    run = _run(db)
    assert run.status is AiRunStatus.FAILED
    assert run.error == str(error)
    assert run.attempts == 1
    assert len(ai.requests) == 1  # the SDK already retried with backoff


def test_a_refusal_fails_the_run(db: Session, use_ai: UseAi) -> None:
    use_ai(reply(text="", stop_reason="refusal", request_id="req_r"))
    run = _run(db)
    assert run.status is AiRunStatus.FAILED
    assert run.error == "The model declined to answer."
    assert run.provider_request_ids == ["req_r"]


def test_a_reply_from_a_fallback_model_is_priced_as_that_model(db: Session, use_ai: UseAi) -> None:
    use_ai(reply(GOOD, model="claude-opus-5-5", input_tokens=100, output_tokens=10))
    run = _run(db)
    assert run.response_model == "claude-opus-5-5"
    assert run.cost_micro_usd == 600  # $4 and $20 per million tokens


def test_without_a_key_the_offline_stand_in_answers(db: Session) -> None:
    run = _run(db)
    assert run.status is AiRunStatus.SUCCEEDED
    assert run.response_model == OFFLINE_MODEL
    assert run.cost_micro_usd == 0
    assert run.response_json is not None
    assert run.response_json["dimension_key"] == "customer_journey"
    assert "sample text" in run.response_json["explanation"][0]
