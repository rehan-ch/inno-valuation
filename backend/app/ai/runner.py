"""Runs one queued AI run to the end. Shared by every touchpoint.

The run already holds its rendered prompts. ``execute`` claims it, calls the model, checks
the answer against the touchpoint's output model and its own checks, and stores the
result. An answer that fails the check is retried once, with the reason added to the
prompt; a second failure fails the run and keeps the raw answer. A call that fails
(timeout, overload, refused request) fails the run at once: the SDK has already retried
it with backoff.

Only one writer may move a run on. Every status change here locks the row and re-reads it
first: a run that is no longer queued or running (the API failed it as stale, or another
worker finished it) is never overwritten. A running run belongs to its worker until its
lease (``stale_after``) runs out, so a message delivered twice calls the model once.

Every attempt adds its tokens, cost and the API's request id to the run, so the log shows
the full use. Log lines name the run id, never any prompt or answer text.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import SDK_MAX_RETRIES, AiError, AiReply, AiRequest, get_ai_client
from app.ai.config import TouchpointSettings, get_ai_config
from app.models import AiRun
from app.models.enums import AiRunStatus

logger = logging.getLogger(__name__)

# The first answer plus one retry with the check's message.
MAX_ATTEMPTS: Final = 2

# Added to the longest possible run when deciding that a run is lost: time in the queue.
STALE_MARGIN: Final = timedelta(minutes=2)

# A run in one of these states may still be moved on.
LIVE: Final = frozenset({AiRunStatus.QUEUED, AiRunStatus.RUNNING})


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


def stale_after(settings: TouchpointSettings) -> timedelta:
    """How long a run may take before it counts as lost: every call the runner and the SDK
    may make at the touchpoint's timeout, plus a margin for the queue."""
    calls = (SDK_MAX_RETRIES + 1) * MAX_ATTEMPTS
    return timedelta(seconds=settings.timeout_seconds * calls) + STALE_MARGIN


def lock(db: Session, run_id: UUID) -> AiRun | None:
    """The run, locked until the transaction ends and re-read as it stands in the database.
    Pending changes on it are flushed first."""
    db.flush()
    return db.execute(
        select(AiRun)
        .where(AiRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def expired(run: AiRun) -> bool:
    """A queued run the API has given up on (or will, the moment anyone asks): older than
    the stale window. Running it now would spend money on an answer nobody reads."""
    if run.status is not AiRunStatus.QUEUED:
        return False
    settings = get_ai_config().touchpoint(run.touchpoint)
    return _now() - run.created_at > stale_after(settings)


def claimable(run: AiRun) -> bool:
    """Queued and not expired, or running past its lease (its worker was lost). A running
    run inside its lease belongs to another worker."""
    if run.status is AiRunStatus.QUEUED:
        return not expired(run)
    if run.status is not AiRunStatus.RUNNING:
        return False
    if run.started_at is None:
        return True
    settings = get_ai_config().touchpoint(run.touchpoint)
    return _now() - run.started_at > stale_after(settings)


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


def mark_failed(db: Session, run: AiRun, error: str) -> bool:
    """Fail a run that is still queued or running, without committing (the caller holds a
    lock until its own commit). Locks and re-reads the row first: a run that finished
    meanwhile is left as it is, and False says so."""
    if lock(db, run.id) is None or run.status not in LIVE:
        return False
    run.status = AiRunStatus.FAILED
    run.error = error
    run.finished_at = _now()
    logger.info("AI run %s (%s) failed: %s", run.id, run.touchpoint, error)
    return True


def _finish(
    db: Session,
    run: AiRun,
    status: AiRunStatus,
    error: str | None = None,
    output: dict[str, Any] | None = None,
) -> None:
    # The use (tokens, cost, request ids, raw answer) is kept whatever happens: the money
    # was spent. The outcome is written only while the run is still ours.
    if lock(db, run.id) is None:
        db.rollback()
        logger.info("AI run %s (%s) is gone; a late %s is dropped", run.id, run.touchpoint, status)
        return
    if run.status not in LIVE:
        db.commit()
        logger.info(
            "AI run %s (%s) was already %s; a late %s is not stored",
            run.id,
            run.touchpoint,
            run.status,
            status,
        )
        return
    run.status = status
    run.error = error
    run.response_json = output
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
    """End a run that cannot go on, keeping whatever it already holds. Commits. A run that
    is no longer queued or running is left as it is."""
    _finish(db, run, AiRunStatus.FAILED, error)


def _claim(db: Session, run: AiRun) -> bool:
    """Take the run for this worker and commit, so no transaction stays open while the
    model works. False, with nothing written, when it is not ours to run."""
    if lock(db, run.id) is None:
        db.rollback()
        logger.info("AI run %s is gone; not run", run.id)
        return False
    if not claimable(run):
        db.commit()
        logger.info("AI run %s (%s) is %s; not run again", run.id, run.touchpoint, run.status)
        return False
    run.status = AiRunStatus.RUNNING
    run.started_at = _now()
    db.commit()
    return True


def execute[T: BaseModel](db: Session, run: AiRun, spec: Touchpoint[T]) -> None:
    """Run ``run`` (queued, or running after a lost worker) to succeeded or failed. A run
    that is finished, or that another worker holds, is left alone."""
    if not _claim(db, run):
        return
    settings = get_ai_config().touchpoint(run.touchpoint)
    if not settings.enabled:
        fail(db, run, f"Touchpoint {run.touchpoint} is switched off in config/ai.yml.")
        return
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
        problem = None
        try:
            reply = client.complete(request)
        except AiError as error:
            problem = str(error)
        else:
            _record(run, reply)
            if reply.stop_reason == "refusal":
                problem = "The model declined to answer."
        if problem is not None:
            fail(db, run, problem)
            return
        try:
            output = parse_output(spec, reply.text)
        except OutputRejectedError as error:
            reason = str(error)
            if reply.stop_reason == "max_tokens":
                reason = f"{reason} The answer was cut off at the token limit."
            logger.info("AI run %s attempt %d rejected: %s", run.id, attempt, reason)
            db.commit()
            # Do not pay for another attempt on a run the API has failed as stale meanwhile.
            if lock(db, run.id) is None or run.status not in LIVE:
                db.commit()
                logger.info("AI run %s is no longer ours; no further attempt", run.id)
                return
            db.commit()
            user = _with_correction(run.user_prompt, reason)
            continue
        _finish(db, run, AiRunStatus.SUCCEEDED, output=output.model_dump(mode="json"))
        return
    fail(db, run, f"The answer failed the check {MAX_ATTEMPTS} times. Last: {reason}")
