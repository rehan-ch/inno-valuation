"""Runs one queued AI run to the end. Shared by every touchpoint.

The run already holds its rendered prompts. ``execute`` marks it running, calls the model,
checks the answer against the touchpoint's output model and its own checks, and stores
the result. An answer that fails the check is retried once, with the reason added to the
prompt; a second failure fails the run and keeps the raw answer (ai-touchpoints rule 4).
A call that fails (timeout, overload, refused request) fails the run at once: the SDK has
already retried it with backoff.

Every attempt adds its tokens, cost and the API's request id to the run, so the log shows
the full use. Log lines name the run id, never any prompt or answer text.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.client import AiError, AiReply, AiRequest, get_ai_client
from app.ai.config import get_ai_config
from app.models import AiRun
from app.models.enums import AiRunStatus

logger = logging.getLogger(__name__)

# The first answer plus one retry with the check's message.
MAX_ATTEMPTS: Final = 2


class OutputRejectedError(ValueError):
    """The answer is not valid JSON, does not fit the schema, or fails a touchpoint check."""


@dataclass(frozen=True)
class Touchpoint[T: BaseModel]:
    """What the runner needs from a touchpoint for one run."""

    output_model: type[T]
    output_schema: dict[str, Any]
    # Checks that need the run's context, such as "names the question's own dimension".
    # Raises OutputRejectedError.
    check: Callable[[T], None]
    # A valid answer for the offline stand-in in development. Never sent anywhere.
    offline_reply: str


def _now() -> datetime:
    return datetime.now(UTC)


def parse_output[T: BaseModel](spec: Touchpoint[T], text: str) -> T:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise OutputRejectedError(f"The answer is not valid JSON ({error.msg}).") from error
    try:
        output = spec.output_model.model_validate(data)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'answer'}: {e['msg']}"
            for e in error.errors(include_url=False, include_input=False)
        )
        raise OutputRejectedError(f"The answer does not fit the schema: {problems}.") from error
    spec.check(output)
    return output


def _with_correction(user_prompt: str, reason: str) -> str:
    return (
        f"{user_prompt}\n\n"
        f"Your previous answer was rejected: {reason} "
        "Answer again, following every rule and the schema exactly."
    )


def _record(run: AiRun, reply: AiReply) -> None:
    run.response_model = reply.model
    run.response_raw = reply.text
    run.stop_reason = reply.stop_reason
    run.input_tokens += reply.input_tokens
    run.output_tokens += reply.output_tokens
    price = get_ai_config().price(reply.model) or get_ai_config().price(run.model)
    if price is not None:
        run.cost_micro_usd += price.cost_micro_usd(reply.input_tokens, reply.output_tokens)
    if reply.request_id:
        run.provider_request_ids = [*run.provider_request_ids, reply.request_id]


def mark_failed(run: AiRun, error: str) -> None:
    """Fail a run without committing, for a caller that holds a lock until its own commit."""
    run.status = AiRunStatus.FAILED
    run.error = error
    run.finished_at = _now()
    logger.info("AI run %s (%s) failed: %s", run.id, run.touchpoint, error)


def _finish(db: Session, run: AiRun, status: AiRunStatus, error: str | None = None) -> None:
    run.status = status
    run.error = error
    run.finished_at = _now()
    db.commit()
    logger.info(
        "AI run %s (%s) %s after %d attempt(s): %d in, %d out, %d micro-USD, requests %s%s",
        run.id,
        run.touchpoint,
        status,
        run.attempts,
        run.input_tokens,
        run.output_tokens,
        run.cost_micro_usd,
        run.provider_request_ids,
        f": {error}" if error else "",
    )


def fail(db: Session, run: AiRun, error: str) -> None:
    """End a run that cannot go on, keeping whatever it already holds. Commits."""
    _finish(db, run, AiRunStatus.FAILED, error)


def execute[T: BaseModel](db: Session, run: AiRun, spec: Touchpoint[T]) -> None:
    """Run ``run`` (queued, or running after a lost worker) to succeeded or failed.
    Commits before the first call, so no transaction stays open while the model works."""
    settings = get_ai_config().touchpoint(run.touchpoint)
    run.status = AiRunStatus.RUNNING
    run.started_at = _now()
    db.commit()
    try:
        client = get_ai_client()
    except AiError as error:
        fail(db, run, str(error))
        return
    user = run.user_prompt
    reason = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        run.attempts = attempt
        request = AiRequest(
            run_id=run.id,
            model=run.model,
            effort=settings.effort,
            max_tokens=settings.max_tokens,
            timeout_seconds=settings.timeout_seconds,
            system=run.system_prompt,
            user=user,
            output_schema=spec.output_schema,
            offline_reply=spec.offline_reply,
        )
        try:
            reply = client.complete(request)
        except AiError as error:
            fail(db, run, str(error))
            return
        _record(run, reply)
        if reply.stop_reason == "refusal":
            fail(db, run, "The model declined to answer.")
            return
        try:
            output = parse_output(spec, reply.text)
        except OutputRejectedError as error:
            reason = str(error)
            if reply.stop_reason == "max_tokens":
                reason = f"{reason} The answer was cut off at the token limit."
            logger.info("AI run %s attempt %d rejected: %s", run.id, attempt, reason)
            db.commit()
            user = _with_correction(run.user_prompt, reason)
            continue
        run.response_json = output.model_dump(mode="json")
        _finish(db, run, AiRunStatus.SUCCEEDED)
        return
    fail(db, run, f"The answer failed the check {MAX_ATTEMPTS} times. Last: {reason}")
