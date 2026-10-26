"""The shared runner: one answer, one retry with the reason, then fail and keep the raw
answer. Every attempt's tokens, cost and request id land on the run."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import yaml
from sqlalchemy.orm import Session

from app.ai import runner
from app.ai.client import (
    OFFLINE_MODEL,
    SDK_MAX_RETRIES,
    AiReply,
    AiRequest,
    AiRequestError,
    AiUnavailableError,
    override_ai_client,
)
from app.ai.config import AI_CONFIG_PATH, AiConfig, TouchpointSettings, get_ai_config
from app.ai.touchpoints import explain_question
from app.models import AiRun
from app.models.enums import AiRunStatus, AiTouchpoint
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


def test_the_stale_window_follows_the_touchpoint_settings() -> None:
    # Every call the runner and the SDK may make at the timeout, plus the queue margin.
    settings = get_ai_config().touchpoint(AiTouchpoint.EXPLAIN_QUESTION)
    calls = (SDK_MAX_RETRIES + 1) * runner.MAX_ATTEMPTS
    assert runner.stale_after(settings) == (
        timedelta(seconds=settings.timeout_seconds * calls) + runner.STALE_MARGIN
    )
    slow = TouchpointSettings(model="m", effort="low", max_tokens=1000, timeout_seconds=300)
    assert runner.stale_after(slow) == timedelta(minutes=30) + runner.STALE_MARGIN
    assert runner.stale_after(slow) > runner.stale_after(settings)


class _FailsTheRunWhileAnswering:
    """The API marks the run stale while the model is still working on it."""

    offline = False

    def __init__(self, db: Session, run: AiRun) -> None:
        self.db, self.run = db, run
        self.calls = 0

    def complete(self, request: AiRequest) -> AiReply:
        self.calls += 1
        assert runner.mark_failed(self.db, self.run, "The run did not finish in time.")
        self.db.commit()
        return reply(GOOD, input_tokens=600, output_tokens=150, request_id="req_late")


def test_a_run_failed_as_stale_is_not_flipped_by_a_late_finish(db: Session) -> None:
    run = AiRunFactory.create()
    client = _FailsTheRunWhileAnswering(db, run)
    override_ai_client(client)
    try:
        runner.execute(db, run, explain_question.spec_for(run))
    finally:
        override_ai_client(None)
    db.refresh(run)
    assert client.calls == 1
    assert run.status is AiRunStatus.FAILED
    assert run.error == "The run did not finish in time."
    assert run.response_json is None
    # The use is still recorded: the money was spent.
    assert (run.input_tokens, run.output_tokens) == (600, 150)
    assert run.provider_request_ids == ["req_late"]


def test_a_run_failed_as_stale_is_not_flipped_by_a_late_failure(db: Session, use_ai: UseAi) -> None:
    use_ai(AiUnavailableError("The AI service did not answer in time."))
    run = AiRunFactory.create()
    assert runner.mark_failed(db, run, "The run did not finish in time.")
    db.commit()
    runner.fail(db, run, "late failure")
    db.refresh(run)
    assert run.error == "The run did not finish in time."


@pytest.mark.parametrize("status", [AiRunStatus.SUCCEEDED, AiRunStatus.FAILED])
def test_mark_failed_leaves_a_finished_run_alone(db: Session, status: AiRunStatus) -> None:
    run = AiRunFactory.create(status=status, error="original")
    assert runner.mark_failed(db, run, "stale") is False
    assert run.status is status
    assert run.error == "original"


def test_a_running_run_inside_its_lease_is_not_claimed(db: Session, use_ai: UseAi) -> None:
    ai = use_ai(reply(GOOD))
    run = AiRunFactory.create(status=AiRunStatus.RUNNING, started_at=datetime.now(UTC))
    runner.execute(db, run, explain_question.spec_for(run))
    assert ai.requests == []
    assert run.status is AiRunStatus.RUNNING
    assert run.attempts == 0


def test_a_running_run_past_its_lease_is_run_again(db: Session, use_ai: UseAi) -> None:
    ai = use_ai(reply(GOOD))
    settings = get_ai_config().touchpoint(AiTouchpoint.EXPLAIN_QUESTION)
    lost = datetime.now(UTC) - runner.stale_after(settings) - timedelta(seconds=1)
    run = AiRunFactory.create(status=AiRunStatus.RUNNING, started_at=lost)
    runner.execute(db, run, explain_question.spec_for(run))
    assert len(ai.requests) == 1
    assert run.status is AiRunStatus.SUCCEEDED


def test_a_disabled_touchpoint_fails_the_run_without_calling_the_ai(
    db: Session, use_ai: UseAi, monkeypatch: pytest.MonkeyPatch
) -> None:
    ai = use_ai(reply(GOOD))
    data: dict[str, Any] = yaml.safe_load(AI_CONFIG_PATH.read_text())
    data["touchpoints"]["explain_question"]["enabled"] = False
    config = AiConfig.model_validate(data)
    monkeypatch.setattr(runner, "get_ai_config", lambda: config)
    run = _run(db)
    assert run.status is AiRunStatus.FAILED
    assert run.error == "Touchpoint explain_question is switched off in config/ai.yml."
    assert ai.requests == []
    assert run.attempts == 0


def test_a_queued_run_older_than_the_stale_window_is_not_run(db: Session, use_ai: UseAi) -> None:
    """The API has given up on it (or will the moment anyone asks), so running it now
    would pay for an answer nobody reads."""
    ai = use_ai(reply(GOOD))
    settings = get_ai_config().touchpoint(AiTouchpoint.EXPLAIN_QUESTION)
    long_ago = datetime.now(UTC) - runner.stale_after(settings) - timedelta(seconds=1)
    run = AiRunFactory.create(status=AiRunStatus.QUEUED, created_at=long_ago)
    assert runner.expired(run)
    assert not runner.claimable(run)
    runner.execute(db, run, explain_question.spec_for(run))
    assert ai.requests == []
    assert run.status is AiRunStatus.QUEUED
