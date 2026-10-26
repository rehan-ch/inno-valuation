"""Explain a readiness question (AI touchpoint 1), saved per organisation and question.

Asking queues an AI run and returns it at once; the page waits for the run to finish.
A finished explanation is reused by everyone in the organisation while it would be asked
in exactly the same words: same model, prompt version and prompts. Changing the company
details the prompt uses, the prompt itself or the model asks again.

A run still waiting is shared too, so two people asking at once start one run. A run left
waiting longer than the touchpoint's ``runner.stale_after`` window (a worker that never
picked it up, or was lost) is failed, and the next ask starts a fresh one. A failed run is
never reused: asking again tries again.

Asks in one organisation are serialised with an advisory lock, so the daily count cannot
be overshot by asks about different questions at the same moment.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Final

from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from app.ai import runner
from app.ai.client import OFFLINE_MODEL, is_offline
from app.ai.config import TouchpointSettings, get_ai_config
from app.ai.prompting import RenderedPrompt
from app.ai.touchpoints import explain_question
from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.jobs.tasks.ai import run_ai
from app.models import AiRun
from app.models.enums import AiRunStatus
from app.scoring.errors import ScoringError
from app.scoring.question_set import QuestionSet, question_set_for
from app.services.organisations import enforce_limit

logger = logging.getLogger(__name__)

# Abuse limit, not a product rule: AI runs cost money. One organisation asking about all
# 60 questions twice over in a day stays well inside it.
DAILY_LIMIT: Final = 150
DAILY_LIMIT_PERIOD: Final = timedelta(days=1)

_PENDING: Final = frozenset({AiRunStatus.QUEUED, AiRunStatus.RUNNING})


def _question_set(version: int, question_id: str) -> QuestionSet:
    """The question set; 404 for an unknown version or question."""
    try:
        question_set = question_set_for(version)
        question_set.dimension_of_question(question_id)
    except ScoringError as error:
        raise AppError("not_found", "Not found.", 404) from error
    return question_set


def _runs(ctx: OrgContext, version: int, question_id: str) -> Select[AiRun]:
    """The organisation's runs for this question, newest first."""
    return (
        select(AiRun)
        .where(
            AiRun.organisation_id == ctx.organisation_id,
            AiRun.touchpoint == explain_question.KEY,
            AiRun.subject_type == explain_question.SUBJECT_TYPE,
            AiRun.subject_id == explain_question.subject_id(version, question_id),
        )
        .order_by(AiRun.created_at.desc(), AiRun.id.desc())
    )


def latest(db: Session, ctx: OrgContext, version: int, question_id: str) -> AiRun | None:
    """The organisation's most recent run for this question, whatever its state."""
    _question_set(version, question_id)
    return db.scalars(_runs(ctx, version, question_id).limit(1)).first()


def _lock_organisation_asks(db: Session, ctx: OrgContext) -> None:
    """Serialise asks in one organisation until the transaction ends: one run per question
    however many people ask at once, and a daily count that cannot be overshot."""
    key = f"{explain_question.KEY}:{ctx.organisation_id}"
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})


def _reusable(
    db: Session,
    ctx: OrgContext,
    *,
    version: int,
    question_id: str,
    settings: TouchpointSettings,
    prompt: RenderedPrompt,
) -> AiRun | None:
    """The newest succeeded or still-waiting run asked in exactly these words. Waiting runs
    that went stale are failed on the way."""
    candidates = db.scalars(
        _runs(ctx, version, question_id).where(
            AiRun.status != AiRunStatus.FAILED,
            AiRun.model == settings.model,
            AiRun.prompt_version == prompt.version,
            AiRun.system_prompt == prompt.system,
            AiRun.user_prompt == prompt.user,
        )
    ).all()
    live = not is_offline()
    now = datetime.now(UTC)
    stale_after = runner.stale_after(settings)
    for run in candidates:
        if run.status in _PENDING and now - run.created_at > stale_after:
            # A no-op if a worker finished it meanwhile; the run is re-read either way.
            runner.mark_failed(db, run, "The run did not finish in time.")
        if run.status is AiRunStatus.FAILED:
            continue
        if run.status in _PENDING:
            return run
        # Sample text from the offline stand-in is never reused once the AI is connected.
        if live and run.response_model == OFFLINE_MODEL:
            continue
        return run
    return None


def request(db: Session, ctx: OrgContext, version: int, question_id: str) -> AiRun:
    """The explanation of one question: a saved one, one on its way, or a new run. Commits."""
    question_set = _question_set(version, question_id)
    settings = get_ai_config().touchpoint(explain_question.KEY)
    if not settings.enabled:
        raise AppError("ai_disabled", "Explanations are switched off.", 409)
    prompt = explain_question.render_prompt(question_set, question_id, ctx.organisation)
    subject = explain_question.subject_id(version, question_id)
    _lock_organisation_asks(db, ctx)
    found = _reusable(
        db, ctx, version=version, question_id=question_id, settings=settings, prompt=prompt
    )
    if found is not None:
        db.commit()  # keeps any stale run failed on the way, and releases the lock
        return found
    enforce_limit(
        db,
        AiRun.created_at,
        AiRun.organisation_id == ctx.organisation_id,
        AiRun.touchpoint == explain_question.KEY,
        limit=DAILY_LIMIT,
        period=DAILY_LIMIT_PERIOD,
        rule=f"Your organisation has asked for {DAILY_LIMIT} explanations in the last day, "
        "the most allowed.",
    )
    run = AiRun(
        organisation_id=ctx.organisation_id,
        touchpoint=explain_question.KEY,
        subject_type=explain_question.SUBJECT_TYPE,
        subject_id=subject,
        requested_by_user_id=ctx.user.id,
        model=settings.model,
        effort=settings.effort,
        prompt_version=prompt.version,
        system_prompt=prompt.system,
        user_prompt=prompt.user,
    )
    db.add(run)
    db.commit()
    try:
        run_ai.delay(str(run.id))
    except BrokerError:
        logger.exception("Could not queue AI run %s", run.id)
        runner.fail(db, run, "The run could not be queued.")
    return run
