"""AI advice on one result (Phase 6; spec 8, 10; AI touchpoints 4, 5, 6 and 8).

The subject is one final readiness result or one confirmed IQ assessment, never both
(spec 4). Advice has four parts, each its own AI run:

- the interpretation (touchpoint 4): what the result means, in words only;
- the gap actions (touchpoint 5): 3 to 5 actions per priority or targeted dimension;
- the recommendations (touchpoint 6): Amy's fixed next steps beside tailored advice;
- the consultation suggestion (touchpoint 8): the AI's judgement, no fixed threshold (Q11).

Nothing here scores, ranks or works out a gap. The facts sent to the AI are the stored
result, the engine's priorities and strengths, and the engine's gaps to today's targets.

Asking queues the runs and returns at once; the page polls. A part is asked for once and
then shared by everyone who may see the result; asking again (``regenerate``) starts a new
run and keeps the old one. A finished interpretation or set of recommendations is copied
into its table with a new version number, linked to its run. A part is ``outdated`` when
it would be asked in different words today (the targets, the company details, the prompt
or the model changed since).

A consultant sees advice on the results they may see, and can never ask for it.
"""

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import ModuleType
from typing import Final, Literal

from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ai import runner
from app.ai.client import OFFLINE_MODEL, is_offline
from app.ai.config import get_ai_config
from app.ai.prompting import RenderedPrompt
from app.ai.schemas.interpret_results import InterpretResultsOutput
from app.ai.schemas.recommendations import RecommendationsOutput
from app.ai.touchpoints import (
    bridge_gaps,
    consultation_nudge,
    explain_question,
    interpret_results,
    propose_iq_scores,
    recommendations,
    results,
)
from app.ai.touchpoints.results import DimensionFact, ResultFacts
from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.jobs.tasks.ai import run_ai
from app.models import AiRun, Interpretation, Recommendation
from app.models.enums import AdviceSubject, AiRunStatus, AiTouchpoint, IqAssessmentStatus
from app.scoring.iq import iq_level, iq_maximum
from app.scoring.priorities import strengths
from app.scoring.question_set import Dimension, IqLevel, QuestionSet
from app.scoring.targets import TargetGap
from app.services import ideas, insights, readiness
from app.services.audit import AuditAction, record
from app.services.organisations import enforce_limit

logger = logging.getLogger(__name__)

# The four parts, in the order the page shows them.
PARTS: Final[dict[AiTouchpoint, ModuleType]] = {
    interpret_results.KEY: interpret_results,
    bridge_gaps.KEY: bridge_gaps,
    recommendations.KEY: recommendations,
    consultation_nudge.KEY: consultation_nudge,
}

# Abuse limit, not a product rule: AI runs cost money. Counts the runs of all four parts,
# so an organisation can ask for full advice 25 times a day.
DAILY_LIMIT: Final = 100
DAILY_LIMIT_PERIOD: Final = timedelta(days=1)

_PENDING: Final = frozenset({AiRunStatus.QUEUED, AiRunStatus.RUNNING})
# How many of a part's newest runs are looked at to find the one to show.
_LOOK_BACK: Final = 20

PartStatus = Literal["off", "none", "pending", "ready", "failed"]


@dataclass(frozen=True, slots=True)
class Subject:
    """One result, with what the AI is told about it and where its audit events point."""

    facts: ResultFacts
    target_type: str
    target_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class Part:
    """One part of the advice as it stands.

    ``status`` is about the newest run: ``off`` (switched off in config/ai.yml), ``none``
    (never asked), ``pending``, ``ready`` or ``failed``. ``run`` is the newest run with an
    answer to show, which may be older than a pending or failed one.
    """

    touchpoint: AiTouchpoint
    status: PartStatus
    run: AiRun | None
    outdated: bool

    @property
    def sample(self) -> bool:
        return self.run is not None and self.run.response_model == OFFLINE_MODEL


@dataclass(frozen=True, slots=True)
class Advice:
    subject: Subject
    parts: dict[AiTouchpoint, Part]
    # Set when their part has an answer to show.
    interpretation: Interpretation | None
    recommendations: list[Recommendation]


# The subject


def _unavailable(version: int) -> AppError:
    return AppError(
        "question_set_unavailable",
        f"This result uses question set version {version}, which is not available here.",
        409,
    )


def readiness_subject(db: Session, ctx: OrgContext, assessment_id: uuid.UUID) -> Subject:
    """A final readiness result of the active organisation; 404 otherwise."""
    assessment = readiness.get_assessment(db, ctx, assessment_id)
    result = readiness.result_of(db, assessment)
    if result is None or assessment.finalised_at is None:
        raise AppError("not_found", "This assessment has no result yet.", 404)
    found = insights.readiness_record(db, assessment, result)
    if found is None:
        raise _unavailable(assessment.question_set_version)
    question_set = found.question_set
    ranks = {str(p["key"]): int(p["rank"]) for p in result.priorities}
    scores = found.scores
    facts = ResultFacts(
        subject=AdviceSubject.READINESS_RESULT,
        subject_id=assessment.id,
        question_set=question_set,
        total=str(result.total),
        total_maximum=str(question_set.total_max),
        band=next(b for b in question_set.readiness_bands if b.key == result.band_key),
        dimensions=tuple(
            _fact(
                d,
                scores[d.key],
                question_set.dimension_max,
                level=None,
                ranks=ranks,
                gaps=found.gaps,
            )
            for d in question_set.dimensions
        ),
        # The engine picks the strengths (a display choice; see scoring.priorities).
        strength_keys=strengths(scores, [int(p["score"]) for p in result.priorities], question_set),
        company=explain_question.company_details(ctx.organisation),
        idea="",
    )
    return Subject(facts=facts, target_type="readiness_assessment", target_id=assessment.id)


def iq_subject(
    db: Session, ctx: OrgContext, idea_id: uuid.UUID, assessment_id: uuid.UUID
) -> Subject:
    """A confirmed IQ assessment of one idea of the active organisation; 404 otherwise."""
    idea = ideas.get_idea(db, ctx, idea_id)
    assessment = ideas.get_assessment(db, ctx, idea, assessment_id)
    if assessment.status is not IqAssessmentStatus.CONFIRMED:
        raise AppError("not_found", "These scores are not confirmed yet.", 404)
    found = insights.iq_record(db, idea, assessment)
    if found is None:
        raise _unavailable(assessment.question_set_version)
    question_set = found.question_set
    ranks = {str(p["key"]): int(p["rank"]) for p in (assessment.priorities or [])}
    scores = found.scores
    priority_scores = [int(p["score"]) for p in (assessment.priorities or [])]
    facts = ResultFacts(
        subject=AdviceSubject.IQ_ASSESSMENT,
        subject_id=assessment.id,
        question_set=question_set,
        total=str(found.iq),
        total_maximum=_whole_or_decimal(iq_maximum(question_set)),
        band=None,
        dimensions=tuple(
            _fact(
                d,
                scores[d.key],
                question_set.iq_scale.max,
                level=_level(question_set, found.rows[d.key].level_key, scores[d.key]),
                ranks=ranks,
                gaps=found.gaps,
            )
            for d in question_set.dimensions
        ),
        strength_keys=strengths(scores, priority_scores, question_set),
        company=explain_question.company_details(ctx.organisation),
        # The idea's own words, never its money (see touchpoint 3).
        idea=propose_iq_scores.idea_details(idea),
    )
    return Subject(facts=facts, target_type="idea", target_id=idea.id)


def _whole_or_decimal(value: Decimal) -> str:
    """``100`` for a whole number, the decimal as it is otherwise. Formatting only."""
    return str(int(value)) if value == value.to_integral_value() else str(value)


def _level(question_set: QuestionSet, level_key: str | None, score: int) -> IqLevel:
    """The level the engine stored at confirmation (spec 3.1), else the engine's level."""
    for level in question_set.iq_levels:
        if level.key == level_key:
            return level
    return iq_level(score, question_set)


def _fact(
    dimension: Dimension,
    score: int,
    maximum: int,
    *,
    level: IqLevel | None,
    ranks: Mapping[str, int],
    gaps: Mapping[str, TargetGap],
) -> DimensionFact:
    key = dimension.key
    gap = gaps.get(key)
    return DimensionFact(
        dimension=dimension,
        score=score,
        maximum=maximum,
        level=level,
        rank=ranks.get(key),
        target=gap.target if gap is not None else None,
        gap=gap.gap if gap is not None else None,
    )


# Reading


def _runs(
    db: Session, ctx: OrgContext, facts: ResultFacts, touchpoint: AiTouchpoint
) -> list[AiRun]:
    """The newest runs of one part for this result, newest first."""
    return list(
        db.scalars(
            select(AiRun)
            .where(
                AiRun.organisation_id == ctx.organisation_id,
                AiRun.touchpoint == touchpoint,
                AiRun.subject_type == facts.subject.value,
                AiRun.subject_id
                == results.subject_id(facts.question_set.version, facts.subject_id),
            )
            .order_by(AiRun.created_at.desc(), AiRun.id.desc())
            .limit(_LOOK_BACK)
        )
    )


def _same_words(run: AiRun, model: str, prompt: RenderedPrompt) -> bool:
    return (
        run.model == model
        and run.prompt_version == prompt.version
        and run.system_prompt == prompt.system
        and run.user_prompt == prompt.user
    )


def _part(db: Session, ctx: OrgContext, facts: ResultFacts, touchpoint: AiTouchpoint) -> Part:
    """One part as it stands. Waiting runs that went stale are failed on the way (the
    caller commits)."""
    settings = get_ai_config().touchpoint(touchpoint)
    if not settings.enabled:
        return Part(touchpoint=touchpoint, status="off", run=None, outdated=False)
    live = not is_offline()
    now = datetime.now(UTC)
    stale_after = runner.stale_after(settings)
    status: PartStatus = "none"
    newest = True
    shown: AiRun | None = None
    for run in _runs(db, ctx, facts, touchpoint):
        if run.status in _PENDING and now - run.created_at > stale_after:
            # The advisory lock first, then the run's row: the order an ask takes them in.
            # A read that took the row first could deadlock with an ask.
            _lock(db, ctx)
            # A no-op if a worker finished it meanwhile; the run is re-read either way.
            runner.mark_failed(db, run, "The run did not finish in time.")
        # Sample text from the offline stand-in is never shown once the AI is connected.
        usable = (
            run.status is AiRunStatus.SUCCEEDED
            and run.response_json is not None
            and not (live and run.response_model == OFFLINE_MODEL)
        )
        if newest:
            if run.status in _PENDING:
                status = "pending"
            elif run.status is AiRunStatus.FAILED:
                status = "failed"
            elif usable:
                status = "ready"
            else:  # a sample from before the AI was connected: as if never asked
                continue
            newest = False
        if usable:
            shown = run
            break
    outdated = shown is not None and not _same_words(
        shown, settings.model, PARTS[touchpoint].render_prompt(facts)
    )
    return Part(touchpoint=touchpoint, status=status, run=shown, outdated=outdated)


def _lock(db: Session, ctx: OrgContext) -> None:
    """Serialise advice requests and version numbering in one organisation until the
    transaction ends: one run per part however many people ask at once."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"advice:{ctx.organisation_id}"},
    )


def _next_version(
    db: Session, model: type[Interpretation] | type[Recommendation], facts: ResultFacts
) -> int:
    newest = db.scalar(
        select(func.max(model.version)).where(
            model.subject_type == facts.subject, model.subject_id == facts.subject_id
        )
    )
    return int(newest or 0) + 1


def _interpretation(db: Session, ctx: OrgContext, facts: ResultFacts, run: AiRun) -> Interpretation:
    """The run's interpretation row, written the first time it is read."""
    by_run = select(Interpretation).where(Interpretation.ai_run_id == run.id)
    row = db.scalar(by_run)
    if row is not None:
        return row
    _lock(db, ctx)
    row = db.scalar(by_run)
    if row is not None:
        return row
    output = InterpretResultsOutput.model_validate(run.response_json)
    row = Interpretation(
        organisation_id=ctx.organisation_id,
        subject_type=facts.subject,
        subject_id=facts.subject_id,
        question_set_version=facts.question_set.version,
        version=_next_version(db, Interpretation, facts),
        summary=list(output.summary),
        per_dimension=[d.model_dump(mode="json") for d in output.dimensions],
        ai_run_id=run.id,
    )
    db.add(row)
    db.flush()
    return row


def _recommendations(
    db: Session, ctx: OrgContext, facts: ResultFacts, run: AiRun
) -> list[Recommendation]:
    """The run's recommendation rows, most urgent first, written the first time they are
    read. The fixed text is the question set's and the rank the engine's, never the AI's."""
    by_run = (
        select(Recommendation)
        .where(Recommendation.ai_run_id == run.id)
        .order_by(Recommendation.priority_rank)
    )
    rows = list(db.scalars(by_run))
    if rows:
        return rows
    _lock(db, ctx)
    rows = list(db.scalars(by_run))
    if rows:
        return rows
    output = RecommendationsOutput.model_validate(run.response_json)
    question_set = facts.question_set
    ranks = {f.dimension.key: f.rank for f in facts.priorities}
    version = _next_version(db, Recommendation, facts)
    for item in output.recommendations:
        rank = ranks.get(item.dimension_key)
        if rank is None:  # unreachable: the run was checked against the priorities it asked
            continue
        rows.append(
            Recommendation(
                organisation_id=ctx.organisation_id,
                subject_type=facts.subject,
                subject_id=facts.subject_id,
                question_set_version=question_set.version,
                version=version,
                dimension_key=item.dimension_key,
                priority_rank=rank,
                fixed_text=question_set.dimension(item.dimension_key).next_steps,
                ai_json=item.model_dump(mode="json", exclude={"dimension_key", "fixed_text"}),
                ai_run_id=run.id,
            )
        )
    db.add_all(rows)
    db.flush()
    return sorted(rows, key=lambda r: r.priority_rank)


def get(db: Session, ctx: OrgContext, subject: Subject) -> Advice:
    """The advice on one result as it stands. Commits (stale runs failed on the way, and
    rows copied from runs that finished since the last read)."""
    facts = subject.facts
    parts = {touchpoint: _part(db, ctx, facts, touchpoint) for touchpoint in PARTS}
    interpreted = parts[interpret_results.KEY].run
    recommended = parts[recommendations.KEY].run
    advice = Advice(
        subject=subject,
        parts=parts,
        interpretation=(
            _interpretation(db, ctx, facts, interpreted) if interpreted is not None else None
        ),
        recommendations=(
            _recommendations(db, ctx, facts, recommended) if recommended is not None else []
        ),
    )
    db.commit()
    return advice


# Asking


def request(
    db: Session,
    ctx: OrgContext,
    subject: Subject,
    *,
    parts: Sequence[AiTouchpoint] | None = None,
    regenerate: bool = False,
) -> None:
    """Ask for advice on one result: every part (or only ``parts``) that has no answer yet,
    or, with ``regenerate``, a fresh run of each. A part that is switched off or already on
    its way is left alone. Commits."""
    facts = subject.facts
    wanted = [t for t in PARTS if parts is None or t in parts]
    _lock(db, ctx)
    config = get_ai_config()
    queued: list[AiRun] = []
    rerun = False
    to_run: list[tuple[AiTouchpoint, RenderedPrompt]] = []
    for touchpoint in wanted:
        part = _part(db, ctx, facts, touchpoint)
        if part.status in ("off", "pending") or (part.status == "ready" and not regenerate):
            continue
        rerun = rerun or part.status != "none"
        to_run.append((touchpoint, PARTS[touchpoint].render_prompt(facts)))
    if not to_run:
        db.commit()  # keeps any stale run failed on the way, and releases the lock
        return
    enforce_limit(
        db,
        AiRun.created_at,
        AiRun.organisation_id == ctx.organisation_id,
        AiRun.touchpoint.in_(list(PARTS)),
        # One ask queues up to four runs: refuse it unless all of them fit under the limit.
        limit=DAILY_LIMIT - len(to_run) + 1,
        period=DAILY_LIMIT_PERIOD,
        rule="Your organisation has asked for AI advice as often as is allowed in one day.",
    )
    subject_id = results.subject_id(facts.question_set.version, facts.subject_id)
    for touchpoint, prompt in to_run:
        settings = config.touchpoint(touchpoint)
        run = AiRun(
            organisation_id=ctx.organisation_id,
            touchpoint=touchpoint,
            subject_type=facts.subject.value,
            subject_id=subject_id,
            requested_by_user_id=ctx.user.id,
            model=settings.model,
            effort=settings.effort,
            prompt_version=prompt.version,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            params=results.keys_param(PARTS[touchpoint].asks_about(facts)),
            # Set here, not by the database: its clock stands still inside a transaction,
            # and the newest run of a part must be unambiguous.
            created_at=datetime.now(UTC),
        )
        db.add(run)
        queued.append(run)
    record(
        db,
        AuditAction.ADVICE_REQUESTED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type=subject.target_type,
        target_id=subject.target_id,
        # Which parts, method version and AI models were asked. Never any text.
        details={
            "subject": facts.subject.value,
            "assessment_id": str(facts.subject_id),
            "question_set_version": facts.question_set.version,
            "parts": [run.touchpoint.value for run in queued],
            "ai_model": ", ".join(sorted({run.model for run in queued})),
            "rerun": rerun,
        },
    )
    db.commit()
    for run in queued:
        try:
            run_ai.delay(str(run.id))
        except BrokerError:
            logger.exception("Could not queue AI run %s", run.id)
            runner.fail(db, run, "The run could not be queued.")
