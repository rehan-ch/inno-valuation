"""Ideas and their IQ assessments: add, score, review, confirm (spec 3, 5, 7; Amy Q1, Q7).

The life of one idea:

- ``draft``: written and edited by its owner (or an owner or admin).
- ``submitted``: sent for scoring. An ``IqAssessment`` is created and the AI proposes a
  score per dimension in the background (touchpoint 3). The proposal is copied into the
  assessment's dimension rows once it is ready. The owner reviews it, changing any score and
  adding a note, and saves as they go.
- ``assessed``: the owner confirmed the scores. The engine computes the IQ, the levels, the
  category scores, the priorities and the Value for Money once, and the assessment never
  changes again. Scoring again creates a new assessment; the confirmed one stays (spec 9).

Who may change an idea: its creator, or anyone with ``ideas.manage`` (owner, admin). The
role is re-read on every change. Changes to an idea, a proposal or a review lock the idea
row, so two tabs cannot race. Audit details never hold idea text or scores: field names and
dimension keys only.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final, Literal

from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.ai import runner
from app.ai.client import OFFLINE_MODEL
from app.ai.config import get_ai_config
from app.ai.schemas.propose_iq_scores import ProposeIqScoresOutput
from app.ai.touchpoints import propose_iq_scores
from app.core.currencies import minor_unit_exponent as currency_exponent
from app.core.currencies import to_major_units, to_minor_units
from app.core.errors import AppError
from app.core.permissions import OrgContext, OrgRole, Permission, has_permission
from app.jobs.tasks.ai import run_ai
from app.models import AiRun, Idea, IqAssessment, IqDimensionScore, User
from app.models.enums import AiRunStatus, IdeaStatus, IqAssessmentStatus
from app.scoring import categories, iq, priorities, vfm
from app.scoring.errors import ScoringError
from app.scoring.question_set import QUESTION_SET, QuestionSet, question_set_for
from app.services import members
from app.services import weights as weights_service
from app.services.audit import AuditAction, record
from app.services.organisations import enforce_limit

logger = logging.getLogger(__name__)

# Abuse limit, not a product rule: AI proposals cost money (the most expensive model, a
# long prompt). A team scoring a dozen ideas, some twice, stays well inside it.
DAILY_LIMIT: Final = 50
DAILY_LIMIT_PERIOD: Final = timedelta(days=1)


# The idea fields a request may set. Money arrives in major units (``investment``,
# ``expected_value``) and is stored in minor units.
TEXT_FIELDS: Final = frozenset(
    {"title", "summary", "problem", "target_market", "uniqueness", "team", "risks", "stage"}
)
MONEY_FIELDS: Final = frozenset({"investment", "expected_value"})
EDITABLE_FIELDS: Final = TEXT_FIELDS | MONEY_FIELDS | {"currency"}

ProposalStatus = Literal["pending", "ready", "failed"]

_PENDING: Final = frozenset({AiRunStatus.QUEUED, AiRunStatus.RUNNING})
_CONFIDENCE_PLACES: Final = Decimal("0.01")


def _not_found() -> AppError:
    return AppError("not_found", "Not found.", 404)


def _forbidden() -> AppError:
    return AppError("forbidden", "You do not have permission to do this.", 403)


def _wrong_status(message: str) -> AppError:
    return AppError("wrong_status", message, 409)


def question_set_of(assessment: IqAssessment) -> QuestionSet:
    """The question set an assessment was proposed on. 409 ``question_set_unavailable`` when
    this server does not have that version, so one old assessment never breaks the rest."""
    try:
        return question_set_for(assessment.question_set_version)
    except ScoringError as error:
        raise AppError(
            "question_set_unavailable",
            f"This assessment uses question set version {assessment.question_set_version}, "
            "which is not available here.",
            409,
        ) from error


# Reading


def _has_confirmed_assessment() -> Any:
    """SQL: the idea has at least one confirmed assessment. A consultant sees only these
    ideas, and keeps seeing them while a newer proposal is on its way (the idea's own
    status is ``submitted`` again then)."""
    return (
        select(IqAssessment.id)
        .where(IqAssessment.idea_id == Idea.id, IqAssessment.status == IqAssessmentStatus.CONFIRMED)
        .exists()
    )


def list_ideas(db: Session, ctx: OrgContext, *, include_archived: bool = False) -> list[Idea]:
    """The organisation's ideas, newest first. A consultant sees ideas with a confirmed
    assessment only."""
    stmt = (
        select(Idea)
        .where(Idea.organisation_id == ctx.organisation_id)
        .order_by(Idea.created_at.desc(), Idea.id.desc())
    )
    if not include_archived:
        stmt = stmt.where(Idea.archived_at.is_(None))
    if ctx.is_consultant:
        stmt = stmt.where(_has_confirmed_assessment())
    return list(db.scalars(stmt))


def get_idea(db: Session, ctx: OrgContext, idea_id: uuid.UUID, *, lock: bool = False) -> Idea:
    """One idea of the active organisation; 404 for another organisation's, and for a
    consultant asking about one without a confirmed assessment. ``lock`` takes it
    ``FOR UPDATE``."""
    stmt = select(Idea).where(Idea.id == idea_id, Idea.organisation_id == ctx.organisation_id)
    if ctx.is_consultant:
        stmt = stmt.where(_has_confirmed_assessment())
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    idea = db.scalar(stmt)
    if idea is None:
        raise _not_found()
    return idea


def assessments_of(db: Session, idea: Idea) -> list[IqAssessment]:
    """Every assessment of the idea, newest first."""
    return list(
        db.scalars(
            select(IqAssessment)
            .where(IqAssessment.idea_id == idea.id)
            .order_by(IqAssessment.created_at.desc(), IqAssessment.id.desc())
        )
    )


def latest_assessment(db: Session, idea: Idea) -> IqAssessment | None:
    return db.scalars(
        select(IqAssessment)
        .where(IqAssessment.idea_id == idea.id)
        .order_by(IqAssessment.created_at.desc(), IqAssessment.id.desc())
        .limit(1)
    ).first()


def get_assessment(
    db: Session, ctx: OrgContext, idea: Idea, assessment_id: uuid.UUID, *, lock: bool = False
) -> IqAssessment:
    """One assessment of ``idea``; 404 for another idea's, and for a consultant asking about
    one that is not confirmed."""
    stmt = select(IqAssessment).where(
        IqAssessment.id == assessment_id, IqAssessment.idea_id == idea.id
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    assessment = db.scalar(stmt)
    if assessment is None or (
        ctx.is_consultant and assessment.status is not IqAssessmentStatus.CONFIRMED
    ):
        raise _not_found()
    return assessment


def run_of(db: Session, assessment: IqAssessment) -> AiRun | None:
    if assessment.ai_run_id is None:
        return None
    return db.get(AiRun, assessment.ai_run_id)


def proposal_status(
    db: Session, assessment: IqAssessment, run: AiRun | None, *, commit: bool = True
) -> ProposalStatus:
    """Where the AI proposal stands. A run left waiting past the touchpoint's stale window
    (a lost worker) is failed on the way, so the page never waits forever. Commits then,
    unless the caller holds a lock and commits itself (``commit=False``)."""
    if assessment.status is IqAssessmentStatus.CONFIRMED:
        return "ready"
    if run is None:
        return "ready" if _scores(db, assessment) else "failed"
    if run.status in _PENDING:
        settings = get_ai_config().touchpoint(run.touchpoint)
        if datetime.now(UTC) - run.created_at > runner.stale_after(settings):
            runner.mark_failed(db, run, "The run did not finish in time.")
            if commit:
                db.commit()
            return "failed"
        return "pending"
    return "ready" if run.status is AiRunStatus.SUCCEEDED else "failed"


def is_sample(run: AiRun | None) -> bool:
    """The proposal came from the offline stand-in, not a real model."""
    return run is not None and run.response_model == OFFLINE_MODEL


@dataclass(frozen=True, slots=True)
class Overview:
    """What a list row needs about one idea, loaded in a few batched queries."""

    latest: IqAssessment | None
    run: AiRun | None
    creator_name: str | None


def overviews(
    db: Session, ideas: list[Idea], *, confirmed_only: bool = False
) -> dict[uuid.UUID, Overview]:
    """Overviews for many ideas at once: a fixed number of queries, not a few per row.
    ``confirmed_only`` (consultants) takes the newest confirmed assessment, not a proposal
    they may not open."""
    ids = [i.id for i in ideas]
    if not ids:
        return {}
    newest = (
        select(IqAssessment)
        .ext(distinct_on(IqAssessment.idea_id))
        .where(IqAssessment.idea_id.in_(ids))
        .order_by(IqAssessment.idea_id, IqAssessment.created_at.desc(), IqAssessment.id.desc())
    )
    if confirmed_only:
        newest = newest.where(IqAssessment.status == IqAssessmentStatus.CONFIRMED)
    latest = {a.idea_id: a for a in db.scalars(newest)}
    run_ids = [a.ai_run_id for a in latest.values() if a.ai_run_id is not None]
    runs = (
        {r.id: r for r in db.scalars(select(AiRun).where(AiRun.id.in_(run_ids)))} if run_ids else {}
    )
    names = user_names(db, {i.created_by_user_id for i in ideas if i.created_by_user_id})
    result = {}
    for idea in ideas:
        found = latest.get(idea.id)
        result[idea.id] = Overview(
            latest=found,
            run=runs.get(found.ai_run_id) if found and found.ai_run_id else None,
            creator_name=names.get(idea.created_by_user_id) if idea.created_by_user_id else None,
        )
    return result


def user_names(db: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    return dict(db.execute(select(User.id, User.name).where(User.id.in_(user_ids))).all())


# Permissions


def may_change(ctx: OrgContext, idea: Idea) -> bool:
    """The caller may edit, submit, review or confirm this idea: its creator with
    ``ideas.create``, or anyone with ``ideas.manage``. False in an archived organisation."""
    if ctx.can(Permission.MANAGE_IDEAS):
        return True
    return ctx.can(Permission.CREATE_IDEAS) and idea.created_by_user_id == ctx.user.id


def _require_may_change(db: Session, ctx: OrgContext, idea: Idea) -> None:
    """``may_change`` with the actor's role re-read now, so a role removed a moment ago no
    longer counts."""
    if ctx.is_archived:
        raise AppError(
            "organisation_archived", "This organisation is archived and cannot be changed.", 403
        )
    membership = members.find_membership(ctx.organisation, db, ctx.user.id)
    if membership is None:
        raise _forbidden()
    role = OrgRole.from_membership(membership.role)
    if has_permission(role, Permission.MANAGE_IDEAS):
        return
    if has_permission(role, Permission.CREATE_IDEAS) and idea.created_by_user_id == ctx.user.id:
        return
    raise _forbidden()


def _require_manager(db: Session, ctx: OrgContext) -> None:
    membership = members.find_membership(ctx.organisation, db, ctx.user.id)
    if membership is None or not has_permission(
        OrgRole.from_membership(membership.role), Permission.MANAGE_IDEAS
    ):
        raise _forbidden()


# Writing the idea


def _money_minor(value: Any, currency: str, field: str) -> int | None:
    """A major-unit amount as minor units of ``currency``; 422 when it has more decimals
    than the currency allows (nothing is rounded in silence)."""
    if value is None:
        return None
    try:
        return to_minor_units(Decimal(value), currency)
    except ValueError as error:
        raise AppError(
            "invalid_amount",
            f"The {field.replace('_', ' ')} has more decimal places than {currency} allows.",
            422,
        ) from error


def create_idea(db: Session, ctx: OrgContext, values: dict[str, Any]) -> Idea:
    """Add a draft idea. Money is given in major units and stored in minor units. Commits."""
    unknown = set(values) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Not settable: {sorted(unknown)}")
    currency = values.get("currency") or ctx.organisation.currency
    idea = Idea(
        organisation_id=ctx.organisation_id,
        currency=currency,
        status=IdeaStatus.DRAFT,
        created_by_user_id=ctx.user.id,
        investment_minor=_money_minor(values.get("investment"), currency, "investment"),
        expected_value_minor=_money_minor(values.get("expected_value"), currency, "expected_value"),
        **{field: values[field] for field in TEXT_FIELDS if field in values},
    )
    db.add(idea)
    db.flush()
    record(
        db,
        AuditAction.IDEA_CREATED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="idea",
        target_id=idea.id,
    )
    db.commit()
    return idea


def _require_editable(db: Session, idea: Idea) -> None:
    """Not archived, and no proposal on its way or waiting for review. A submitted idea
    whose proposal failed becomes a draft again, so it can be changed and rescored."""
    if idea.archived_at is not None:
        raise _wrong_status("This idea is archived. Restore it to change it.")
    if idea.status is not IdeaStatus.SUBMITTED:
        return
    standing = _latest_proposal_standing(db, idea)
    if standing == "pending":
        raise _wrong_status("This idea is being scored. Wait for the proposal, then change it.")
    if standing == "ready":
        raise _wrong_status(
            "This idea has a proposal waiting for review. Confirm or replace it first."
        )
    idea.status = IdeaStatus.DRAFT


def update_idea(db: Session, ctx: OrgContext, idea_id: uuid.UUID, changes: dict[str, Any]) -> Idea:
    """Change the fields sent. Not while a proposal is being made (the AI is reading the
    idea as it stands) and not when archived. The audit event lists field names only.
    Commits."""
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Not editable: {sorted(unknown)}")
    idea = get_idea(db, ctx, idea_id, lock=True)
    _require_may_change(db, ctx, idea)
    _require_editable(db, idea)

    currency = changes.get("currency") or idea.currency
    before = {field: getattr(idea, field) for field in TEXT_FIELDS}
    before.update(
        currency=idea.currency,
        investment=idea.investment_minor,
        expected_value=idea.expected_value_minor,
    )
    for field in TEXT_FIELDS:
        if field in changes:
            setattr(idea, field, changes[field])
    if currency != idea.currency:
        # Keep the amounts' value; re-encode them in the new currency's minor units.
        for field, column in (
            ("investment", "investment_minor"),
            ("expected_value", "expected_value_minor"),
        ):
            if field not in changes and getattr(idea, column) is not None:
                changes[field] = to_major_units(getattr(idea, column), idea.currency)
        idea.currency = currency
    for field, column in (
        ("investment", "investment_minor"),
        ("expected_value", "expected_value_minor"),
    ):
        if field in changes:
            setattr(idea, column, _money_minor(changes[field], currency, field))
    after = {field: getattr(idea, field) for field in TEXT_FIELDS}
    after.update(
        currency=idea.currency,
        investment=idea.investment_minor,
        expected_value=idea.expected_value_minor,
    )
    changed = sorted(field for field in after if after[field] != before[field])
    if changed:
        record(
            db,
            AuditAction.IDEA_UPDATED,
            actor=ctx.user,
            organisation_id=ctx.organisation_id,
            target_type="idea",
            target_id=idea.id,
            details={"fields": changed},
        )
    db.commit()
    return idea


def archive_idea(db: Session, ctx: OrgContext, idea_id: uuid.UUID) -> Idea:
    """Hide an idea from the list. Its assessments stay. Owners and admins only. Commits."""
    idea = get_idea(db, ctx, idea_id, lock=True)
    _require_manager(db, ctx)
    if idea.archived_at is None:
        idea.archived_at = datetime.now(UTC)
        record(
            db,
            AuditAction.IDEA_ARCHIVED,
            actor=ctx.user,
            organisation_id=ctx.organisation_id,
            target_type="idea",
            target_id=idea.id,
        )
    db.commit()
    return idea


def restore_idea(db: Session, ctx: OrgContext, idea_id: uuid.UUID) -> Idea:
    idea = get_idea(db, ctx, idea_id, lock=True)
    _require_manager(db, ctx)
    if idea.archived_at is not None:
        idea.archived_at = None
        record(
            db,
            AuditAction.IDEA_RESTORED,
            actor=ctx.user,
            organisation_id=ctx.organisation_id,
            target_type="idea",
            target_id=idea.id,
        )
    db.commit()
    return idea


# Proposing


def _latest_proposal_standing(db: Session, idea: Idea) -> ProposalStatus | None:
    """Where the latest unconfirmed proposal stands, under the caller's lock (no commit);
    None when the latest assessment is confirmed or superseded, or there is none."""
    latest = latest_assessment(db, idea)
    if latest is None or latest.status is not IqAssessmentStatus.PROPOSED:
        return None
    return proposal_status(db, latest, run_of(db, latest), commit=False)


def request_assessment(db: Session, ctx: OrgContext, idea_id: uuid.UUID) -> IqAssessment:
    """Send the idea for scoring: a new assessment whose AI proposal is queued. An earlier
    proposal that was never confirmed is superseded; a confirmed one stays for history.
    409 while a proposal is still on its way. Commits."""
    idea = get_idea(db, ctx, idea_id, lock=True)
    _require_may_change(db, ctx, idea)
    if idea.archived_at is not None:
        raise _wrong_status("This idea is archived. Restore it to score it.")
    settings = get_ai_config().touchpoint(propose_iq_scores.KEY)
    if not settings.enabled:
        raise AppError("ai_disabled", "Scoring proposals are switched off.", 409)

    latest = latest_assessment(db, idea)
    if latest is not None and latest.status is IqAssessmentStatus.PROPOSED:
        # No commit here: the idea lock must hold until the new assessment is written.
        if proposal_status(db, latest, run_of(db, latest), commit=False) == "pending":
            raise AppError(
                "proposal_pending", "A proposal for this idea is already on its way.", 409
            )
        latest.status = IqAssessmentStatus.SUPERSEDED
    enforce_limit(
        db,
        AiRun.created_at,
        AiRun.organisation_id == ctx.organisation_id,
        AiRun.touchpoint == propose_iq_scores.KEY,
        limit=DAILY_LIMIT,
        period=DAILY_LIMIT_PERIOD,
        rule=f"Your organisation has asked for {DAILY_LIMIT} scoring proposals in the last "
        "day, the most allowed.",
    )
    prompt = propose_iq_scores.render_prompt(QUESTION_SET, idea, ctx.organisation)
    assessment = IqAssessment(
        organisation_id=ctx.organisation_id,
        idea_id=idea.id,
        question_set_version=QUESTION_SET.version,
        status=IqAssessmentStatus.PROPOSED,
        requested_by_user_id=ctx.user.id,
        # Set here, not by the database: inside one transaction now() is the same for every
        # row, and "the latest assessment" must be the one asked for last.
        created_at=datetime.now(UTC),
    )
    db.add(assessment)
    db.flush()
    run = AiRun(
        organisation_id=ctx.organisation_id,
        touchpoint=propose_iq_scores.KEY,
        subject_type=propose_iq_scores.SUBJECT_TYPE,
        subject_id=propose_iq_scores.subject_id(QUESTION_SET.version, assessment.id),
        requested_by_user_id=ctx.user.id,
        model=settings.model,
        effort=settings.effort,
        prompt_version=prompt.version,
        system_prompt=prompt.system,
        user_prompt=prompt.user,
    )
    db.add(run)
    db.flush()
    assessment.ai_run_id = run.id
    idea.status = IdeaStatus.SUBMITTED
    record(
        db,
        AuditAction.IQ_REQUESTED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="idea",
        target_id=idea.id,
        details={"assessment_id": str(assessment.id)},
    )
    db.commit()
    try:
        run_ai.delay(str(run.id))
    except BrokerError:
        logger.exception("Could not queue AI run %s", run.id)
        runner.fail(db, run, "The run could not be queued.")
    return assessment


def _scores(db: Session, assessment: IqAssessment) -> list[IqDimensionScore]:
    return list(
        db.scalars(select(IqDimensionScore).where(IqDimensionScore.assessment_id == assessment.id))
    )


def load_scores(
    db: Session, assessment: IqAssessment, *, commit: bool = True
) -> list[IqDimensionScore]:
    """The assessment's dimension rows in book order. Written from the AI run's answer the
    first time they are asked for after it succeeds, under the assessment lock so two
    readers do not both write them. Empty while the proposal is on its way or failed.
    Commits when it writes, unless the caller holds a lock and commits itself."""
    question_set = question_set_of(assessment)
    order = {key: i for i, key in enumerate(question_set.dimension_keys)}
    rows = _scores(db, assessment)
    if not rows:
        run = run_of(db, assessment)
        if run is None or run.status is not AiRunStatus.SUCCEEDED or run.response_json is None:
            return []
        db.execute(
            select(IqAssessment.id).where(IqAssessment.id == assessment.id).with_for_update()
        )
        rows = _scores(db, assessment)  # another request may have written them meanwhile
        if not rows:
            output = ProposeIqScoresOutput.model_validate(run.response_json)
            for proposed in output.scores:
                rows.append(
                    IqDimensionScore(
                        organisation_id=assessment.organisation_id,
                        assessment_id=assessment.id,
                        dimension_key=proposed.dimension_key,
                        proposed_score=proposed.score,
                        proposed_rationale=list(proposed.rationale),
                        proposed_confidence=Decimal(str(proposed.confidence)).quantize(
                            _CONFIDENCE_PLACES, ROUND_HALF_UP
                        ),
                    )
                )
            db.add_all(rows)
            if commit:
                db.commit()
            else:
                db.flush()
    return sorted(rows, key=lambda r: order.get(r.dimension_key, len(order)))


def missing_information(run: AiRun | None) -> list[str]:
    """The AI's open questions about the idea, if the proposal is ready."""
    if run is None or run.status is not AiRunStatus.SUCCEEDED or run.response_json is None:
        return []
    return [str(q) for q in run.response_json.get("missing_information", [])]


# Reviewing and confirming


def _require_reviewable(db: Session, ctx: OrgContext, idea: Idea, assessment: IqAssessment) -> None:
    _require_may_change(db, ctx, idea)
    if assessment.status is IqAssessmentStatus.CONFIRMED:
        raise _wrong_status(
            "This assessment is confirmed and cannot change. Score the idea again instead."
        )
    if assessment.status is IqAssessmentStatus.SUPERSEDED:
        raise _wrong_status("A newer proposal has replaced this one.")


def _validate_final(question_set: QuestionSet, scores: dict[str, int | None]) -> None:
    scale = question_set.iq_scale
    for key, value in scores.items():
        try:
            question_set.dimension(key)
        except ScoringError as error:
            raise AppError("invalid_scores", str(error), 422) from error
        if value is not None and not scale.min <= value <= scale.max:
            raise AppError(
                "invalid_scores", f"Score for {key} must be {scale.min} to {scale.max}.", 422
            )


def save_review(
    db: Session,
    ctx: OrgContext,
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    *,
    scores: dict[str, int | None],
    notes: dict[str, str | None],
) -> IqAssessment:
    """Merge the owner's changed scores and notes into the review (``None`` puts a score back
    to the proposal or clears a note). Saved as they go, so the review can be resumed.
    Commits."""
    idea = get_idea(db, ctx, idea_id, lock=True)
    assessment = get_assessment(db, ctx, idea, assessment_id)
    _require_reviewable(db, ctx, idea, assessment)
    rows = load_scores(db, assessment, commit=False)  # the idea lock holds until the commit
    if not rows:
        raise AppError("proposal_not_ready", "The proposed scores are not ready yet.", 409)
    question_set = question_set_of(assessment)
    _validate_final(question_set, scores)
    try:
        for key in notes:
            question_set.dimension(key)
    except ScoringError as error:
        raise AppError("invalid_scores", str(error), 422) from error
    by_key = {row.dimension_key: row for row in rows}
    for key, value in scores.items():
        row = by_key[key]
        row.final_score = value
        row.reviewed_by_user_id = ctx.user.id
    for key, note in notes.items():
        text = (note or "").strip()  # length is checked by the schema (NOTE_MAX_LENGTH)
        by_key[key].note = text or None
        by_key[key].reviewed_by_user_id = ctx.user.id
    db.commit()
    return assessment


def confirm(
    db: Session, ctx: OrgContext, idea_id: uuid.UUID, assessment_id: uuid.UUID
) -> IqAssessment:
    """Make the reviewed scores final and compute the result with the engine: IQ (spec 3.2),
    levels (3.1), category scores (3.6), priorities (7) and Value for Money (5.1) from the
    idea's investment as it stands now. Written once; the assessment is immutable afterwards.
    Commits."""
    idea = get_idea(db, ctx, idea_id, lock=True)
    assessment = get_assessment(db, ctx, idea, assessment_id)
    _require_reviewable(db, ctx, idea, assessment)
    question_set = question_set_of(assessment)
    rows = load_scores(db, assessment, commit=False)  # the idea lock holds until the commit
    if len(rows) != len(question_set.dimensions):
        raise AppError("proposal_not_ready", "The proposed scores are not ready yet.", 409)
    final = {
        row.dimension_key: row.final_score if row.final_score is not None else row.proposed_score
        for row in rows
    }
    try:
        scored = iq.score_iq(final, question_set=question_set)
        by_category = categories.iq_categories(scored, question_set)
        # The organisation's dimension importance only orders tied priorities; it never
        # changes a score (Amy Q2). PROVISIONAL: see open-questions Q23 (tie-break only).
        weights = weights_service.current_weights(db, ctx.organisation_id, question_set)
        ranked = priorities.iq_priorities(scored, weights, question_set=question_set)
        # Spec 5.1 with the IQ the user sees (Q18): cost per innovation point, or None.
        per_point = vfm.vfm(
            idea.investment_minor, currency_exponent(idea.currency), scored.iq, question_set
        )
    except ScoringError as error:
        raise AppError("invalid_scores", str(error), 422) from error
    if scored.iq is None:  # unreachable: every row has a proposed score once loaded
        raise AppError("invalid_scores", "Every dimension needs a score.", 422)

    levels = {d.key: d.level for d in scored.dimensions}
    changed = []
    for row in rows:
        row.final_score = final[row.dimension_key]
        level = levels[row.dimension_key]
        row.level_key = level.key if level is not None else None
        if row.reviewed_by_user_id is None:
            row.reviewed_by_user_id = ctx.user.id
        if row.final_score != row.proposed_score:
            changed.append(row.dimension_key)
    now = datetime.now(UTC)
    assessment.iq = scored.iq
    assessment.category_scores = {c.key: str(c.score) for c in by_category.categories}
    assessment.priorities = [{"rank": p.rank, "key": p.key, "score": p.score} for p in ranked.items]
    assessment.weights_snapshot = weights_service.snapshot(weights)
    assessment.investment_minor = idea.investment_minor
    assessment.currency = idea.currency
    assessment.vfm_per_point = per_point
    assessment.status = IqAssessmentStatus.CONFIRMED
    assessment.confirmed_by_user_id = ctx.user.id
    assessment.confirmed_at = now
    idea.status = IdeaStatus.ASSESSED
    record(
        db,
        AuditAction.IQ_CONFIRMED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="iq_assessment",
        target_id=assessment.id,
        details={"changed": changed},
    )
    db.commit()
    return assessment


def confirmed_count(db: Session, ctx: OrgContext) -> int:
    count = db.scalar(
        select(func.count())
        .select_from(IqAssessment)
        .where(
            IqAssessment.organisation_id == ctx.organisation_id,
            IqAssessment.status == IqAssessmentStatus.CONFIRMED,
        )
    )
    return int(count or 0)
