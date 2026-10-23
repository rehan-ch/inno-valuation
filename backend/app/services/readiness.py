"""Readiness assessments: start, answer, agree, finalise (spec 2, Amy Q5).

The life of one assessment, never backwards:

- ``collecting``: everyone who may answer fills in their own 60 answers, saved as they go,
  then submits them (all 60 required, spec 2.8).
- ``consensus``: the facilitator (owner or admin) sees every submitted answer, the mean
  per question (2 decimals) and the spread, and sets the agreed answer per question.
  People who never submitted are left out; answering is closed.
- ``final``: scored by the engine from the agreed answers only, all 60 required (spec 2.7).
  The result is written once and never changed.

One assessment may be open (not final) per organisation at a time. Status changes lock the
assessment row (``FOR UPDATE``); saving answers takes a share lock, so a save never lands
after consensus began. A manager's role is re-read under the lock, like team changes.
Audit details never hold answers or scores.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager

from app.core.errors import AppError
from app.core.permissions import OrgContext, OrgRole, Permission, has_permission
from app.models import (
    ReadinessAssessment,
    ReadinessConsensus,
    ReadinessResponse,
    ReadinessResult,
    User,
)
from app.models.enums import ReadinessStatus
from app.scoring import categories, priorities, readiness
from app.scoring.errors import ScoringError
from app.scoring.question_set import QUESTION_SET, QuestionSet, question_set_for
from app.services import members
from app.services.audit import AuditAction, record
from app.services.organisations import lock_organisation

# PROVISIONAL (display only, not scoring): a question is highlighted for discussion when
# answers are this far apart. Amy has not set a threshold; it changes no number.
WIDE_SPREAD: Final = 2

NOTE_MAX_LENGTH: Final = 2000

_MEAN_PLACES: Final = Decimal("0.01")


def _not_found() -> AppError:
    return AppError("not_found", "Not found.", 404)


def _wrong_status(message: str) -> AppError:
    return AppError("wrong_status", message, 409)


def _invalid_answers(error: ScoringError) -> AppError:
    return AppError("invalid_answers", str(error), 422)


# Reading


def list_assessments(db: Session, ctx: OrgContext) -> list[ReadinessAssessment]:
    """The organisation's assessments, newest first. A consultant sees final ones only."""
    stmt = (
        select(ReadinessAssessment)
        .where(ReadinessAssessment.organisation_id == ctx.organisation_id)
        .order_by(ReadinessAssessment.created_at.desc())
    )
    if ctx.is_consultant:
        stmt = stmt.where(ReadinessAssessment.status == ReadinessStatus.FINAL)
    return list(db.scalars(stmt))


def get_assessment(
    db: Session, ctx: OrgContext, assessment_id: uuid.UUID, *, lock: str | None = None
) -> ReadinessAssessment:
    """One assessment of the active organisation; 404 for another organisation's, and for
    a consultant asking about one that is not final. ``lock`` is "update" or "share"."""
    stmt = select(ReadinessAssessment).where(
        ReadinessAssessment.id == assessment_id,
        ReadinessAssessment.organisation_id == ctx.organisation_id,
    )
    if lock == "update":
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    elif lock == "share":
        stmt = stmt.with_for_update(read=True).execution_options(populate_existing=True)
    assessment = db.scalar(stmt)
    if assessment is None:
        raise _not_found()
    if ctx.is_consultant and assessment.status is not ReadinessStatus.FINAL:
        raise _not_found()
    return assessment


def own_response(
    db: Session, assessment: ReadinessAssessment, user_id: uuid.UUID, *, lock: bool = False
) -> ReadinessResponse | None:
    """The person's own response. ``lock`` takes the row ``FOR UPDATE`` and re-reads it, so
    two saves (two tabs) or a save racing a submit cannot overwrite each other."""
    stmt = select(ReadinessResponse).where(
        ReadinessResponse.assessment_id == assessment.id,
        ReadinessResponse.user_id == user_id,
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalar(stmt)


def responses(db: Session, assessment: ReadinessAssessment) -> list[ReadinessResponse]:
    """Every response with its person loaded, in the order people started."""
    return list(
        db.scalars(
            select(ReadinessResponse)
            .join(ReadinessResponse.user)
            .options(contains_eager(ReadinessResponse.user))
            .where(ReadinessResponse.assessment_id == assessment.id)
            .order_by(ReadinessResponse.created_at)
        )
    )


def submitted_count(db: Session, assessment: ReadinessAssessment) -> int:
    count = db.scalar(
        select(func.count())
        .select_from(ReadinessResponse)
        .where(
            ReadinessResponse.assessment_id == assessment.id,
            ReadinessResponse.submitted_at.is_not(None),
        )
    )
    return int(count or 0)


@dataclass(frozen=True, slots=True)
class Overview:
    """What a list row needs about one assessment, loaded in a few batched queries."""

    submitted_count: int
    result: ReadinessResult | None
    creator_name: str | None
    own: ReadinessResponse | None


def overviews(
    db: Session, user_id: uuid.UUID, assessments: list[ReadinessAssessment]
) -> dict[uuid.UUID, Overview]:
    """Overviews for many assessments at once: a fixed number of queries, not a few per row."""
    ids = [a.id for a in assessments]
    if not ids:
        return {}
    counts: dict[uuid.UUID, int] = dict(
        db.execute(
            select(ReadinessResponse.assessment_id, func.count())
            .where(
                ReadinessResponse.assessment_id.in_(ids),
                ReadinessResponse.submitted_at.is_not(None),
            )
            .group_by(ReadinessResponse.assessment_id)
        ).all()
    )
    results = {
        r.assessment_id: r
        for r in db.scalars(select(ReadinessResult).where(ReadinessResult.assessment_id.in_(ids)))
    }
    creator_ids = {a.created_by_user_id for a in assessments if a.created_by_user_id}
    names: dict[uuid.UUID, str] = (
        dict(db.execute(select(User.id, User.name).where(User.id.in_(creator_ids))).all())
        if creator_ids
        else {}
    )
    own = {
        r.assessment_id: r
        for r in db.scalars(
            select(ReadinessResponse).where(
                ReadinessResponse.assessment_id.in_(ids), ReadinessResponse.user_id == user_id
            )
        )
    }
    return {
        a.id: Overview(
            submitted_count=counts.get(a.id, 0),
            result=results.get(a.id),
            creator_name=names.get(a.created_by_user_id) if a.created_by_user_id else None,
            own=own.get(a.id),
        )
        for a in assessments
    }


# Starting


def start_assessment(db: Session, ctx: OrgContext) -> ReadinessAssessment:
    """Open a new assessment for answers. 409 while another one is still open. Commits."""
    lock_organisation(db, ctx.organisation)
    members.actor_role(ctx.organisation, db, ctx)
    open_one = db.scalar(
        select(ReadinessAssessment.id).where(
            ReadinessAssessment.organisation_id == ctx.organisation_id,
            ReadinessAssessment.status != ReadinessStatus.FINAL,
        )
    )
    if open_one is not None:
        raise AppError(
            "assessment_open",
            "An assessment is already in progress. Finish it before starting another.",
            409,
        )
    now = datetime.now(UTC)
    assessment = ReadinessAssessment(
        organisation_id=ctx.organisation_id,
        question_set_version=QUESTION_SET.version,
        status=ReadinessStatus.COLLECTING,
        created_by_user_id=ctx.user.id,
        started_at=now,
    )
    db.add(assessment)
    db.flush()
    record(
        db,
        AuditAction.READINESS_STARTED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="readiness_assessment",
        target_id=assessment.id,
    )
    db.commit()
    return assessment


# Answering


def _require_can_answer(db: Session, ctx: OrgContext) -> None:
    """The actor's role, re-read now, still allows answering."""
    membership = members.find_membership(ctx.organisation, db, ctx.user.id)
    if membership is None or not has_permission(
        OrgRole.from_membership(membership.role), Permission.ANSWER_ASSESSMENT
    ):
        raise AppError("forbidden", "You do not have permission to do this.", 403)


def save_answers(
    db: Session,
    ctx: OrgContext,
    assessment_id: uuid.UUID,
    changes: dict[str, int | None],
) -> ReadinessResponse:
    """Merge ``changes`` into the actor's own answers (``None`` clears one). Commits.

    Allowed while the assessment collects answers and the actor has not submitted.
    """
    assessment = get_assessment(db, ctx, assessment_id, lock="share")
    if assessment.status is not ReadinessStatus.COLLECTING:
        raise _wrong_status("Answers are closed: the team is agreeing its answers now.")
    _require_can_answer(db, ctx)
    question_set = question_set_for(assessment.question_set_version)
    try:
        readiness.validate_answers(changes, question_set)
    except ScoringError as error:
        raise _invalid_answers(error) from error

    if own_response(db, assessment, ctx.user.id) is None:
        try:
            with db.begin_nested():
                db.add(
                    ReadinessResponse(
                        organisation_id=ctx.organisation_id,
                        assessment_id=assessment.id,
                        user_id=ctx.user.id,
                        answers={},
                    )
                )
                db.flush()
        except IntegrityError:
            pass  # a save from another tab created it a moment ago
    # Merge under the row lock: a parallel save waits and then sees this one's answers.
    response = own_response(db, assessment, ctx.user.id, lock=True)
    if response is None:  # deleted between the insert and the lock: user gone
        raise _not_found()
    if response.submitted_at is not None:
        raise _wrong_status("Your answers are already submitted.")

    merged = dict(response.answers)
    for question_id, value in changes.items():
        if value is None:
            merged.pop(question_id, None)
        else:
            merged[question_id] = value
    response.answers = merged
    db.commit()
    return response


def submit_answers(db: Session, ctx: OrgContext, assessment_id: uuid.UUID) -> ReadinessResponse:
    """Submit the actor's own answers; all of the questions are required (spec 2.8). Commits."""
    assessment = get_assessment(db, ctx, assessment_id, lock="share")
    if assessment.status is not ReadinessStatus.COLLECTING:
        raise _wrong_status("Answers are closed: the team is agreeing its answers now.")
    _require_can_answer(db, ctx)
    # Locked, so a save still in flight finishes first and is counted.
    response = own_response(db, assessment, ctx.user.id, lock=True)
    question_set = question_set_for(assessment.question_set_version)
    answered = response.answers if response is not None else {}
    missing = [q for q in question_set.all_question_ids() if q not in answered]
    if response is None or missing:
        raise AppError(
            "answers_incomplete",
            f"Answer every question before submitting: {len(missing)} still to answer.",
            422,
        )
    if response.submitted_at is not None:
        raise _wrong_status("Your answers are already submitted.")
    response.submitted_at = datetime.now(UTC)
    record(
        db,
        AuditAction.READINESS_RESPONSE_SUBMITTED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="readiness_assessment",
        target_id=assessment.id,
    )
    db.commit()
    return response


# Consensus


def begin_consensus(db: Session, ctx: OrgContext, assessment_id: uuid.UUID) -> ReadinessAssessment:
    """Close answering and let the facilitator agree the answers. Needs at least one
    submitted response; people who did not submit are left out. Commits."""
    assessment = get_assessment(db, ctx, assessment_id, lock="update")
    members.actor_role(ctx.organisation, db, ctx)
    if assessment.status is not ReadinessStatus.COLLECTING:
        raise _wrong_status("Agreeing the answers has already started.")
    if submitted_count(db, assessment) == 0:
        raise AppError(
            "no_submissions", "Nobody has submitted answers yet, so there is nothing to agree.", 409
        )
    assessment.status = ReadinessStatus.CONSENSUS
    db.add(
        ReadinessConsensus(
            organisation_id=ctx.organisation_id,
            assessment_id=assessment.id,
            answers={},
            notes={},
            set_by_user_id=ctx.user.id,
        )
    )
    record(
        db,
        AuditAction.READINESS_CONSENSUS_STARTED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="readiness_assessment",
        target_id=assessment.id,
        details={"submitted": submitted_count(db, assessment)},
    )
    db.commit()
    return assessment


def consensus_of(db: Session, assessment: ReadinessAssessment) -> ReadinessConsensus | None:
    return db.scalar(
        select(ReadinessConsensus).where(ReadinessConsensus.assessment_id == assessment.id)
    )


@dataclass(frozen=True, slots=True)
class PersonAnswer:
    user_id: uuid.UUID
    name: str
    answer: int


@dataclass(frozen=True, slots=True)
class QuestionConsensus:
    question_id: str
    dimension_key: str
    answers: tuple[PersonAnswer, ...]
    mean: Decimal | None
    spread: int | None
    agreed: int | None
    note: str | None

    @property
    def wide_spread(self) -> bool:
        return self.spread is not None and self.spread >= WIDE_SPREAD


def mean_of(values: list[int]) -> Decimal:
    """Mean to 2 decimals, halves rounded up like the scoring engine (spec 2.8)."""
    return (Decimal(sum(values)) / Decimal(len(values))).quantize(_MEAN_PLACES, ROUND_HALF_UP)


def consensus_table(
    db: Session, assessment: ReadinessAssessment, submitted: list[ReadinessResponse]
) -> list[QuestionConsensus]:
    """Per question, in book order: each submitted answer, the mean, the spread, and the
    agreed answer and note so far. ``submitted`` is the submitted responses, people loaded."""
    question_set: QuestionSet = question_set_for(assessment.question_set_version)
    consensus = consensus_of(db, assessment)
    agreed = consensus.answers if consensus is not None else {}
    notes = consensus.notes if consensus is not None else {}
    rows = []
    for dimension in question_set.dimensions:
        for question in dimension.questions:
            given = [
                PersonAnswer(
                    user_id=r.user_id, name=r.user.name, answer=int(r.answers[question.id])
                )
                for r in submitted
                if question.id in r.answers
            ]
            values = [p.answer for p in given]
            rows.append(
                QuestionConsensus(
                    question_id=question.id,
                    dimension_key=dimension.key,
                    answers=tuple(given),
                    mean=mean_of(values) if values else None,
                    spread=max(values) - min(values) if values else None,
                    agreed=agreed.get(question.id),
                    note=notes.get(question.id),
                )
            )
    return rows


def save_consensus(
    db: Session,
    ctx: OrgContext,
    assessment_id: uuid.UUID,
    *,
    answers: dict[str, int | None],
    notes: dict[str, str | None],
) -> ReadinessConsensus:
    """Merge agreed answers and notes (``None`` or a blank note clears one). Commits."""
    assessment = get_assessment(db, ctx, assessment_id, lock="update")
    members.actor_role(ctx.organisation, db, ctx)
    if assessment.status is not ReadinessStatus.CONSENSUS:
        raise _wrong_status("Agreed answers can only be set while the team is agreeing them.")
    question_set = question_set_for(assessment.question_set_version)
    try:
        readiness.validate_answers(answers, question_set)
        for question_id in notes:
            question_set.dimension_of_question(question_id)
    except ScoringError as error:
        raise _invalid_answers(error) from error

    consensus = consensus_of(db, assessment)
    if consensus is None:  # begin_consensus always writes one; guard against a bad row
        raise _wrong_status("Agreeing the answers has not started.")
    merged_answers = dict(consensus.answers)
    for question_id, value in answers.items():
        if value is None:
            merged_answers.pop(question_id, None)
        else:
            merged_answers[question_id] = value
    merged_notes = dict(consensus.notes)
    for question_id, note in notes.items():
        text = (note or "").strip()
        if text:
            merged_notes[question_id] = text[:NOTE_MAX_LENGTH]
        else:
            merged_notes.pop(question_id, None)
    consensus.answers = merged_answers
    consensus.notes = merged_notes
    consensus.set_by_user_id = ctx.user.id
    db.commit()
    return consensus


# Finalising


def finalise(db: Session, ctx: OrgContext, assessment_id: uuid.UUID) -> ReadinessResult:
    """Score the agreed answers with the engine and close the assessment for good.

    All of the agreed answers are required (spec 2.7). Commits.
    """
    assessment = get_assessment(db, ctx, assessment_id, lock="update")
    members.actor_role(ctx.organisation, db, ctx)
    if assessment.status is not ReadinessStatus.CONSENSUS:
        raise _wrong_status("Only an assessment whose answers are being agreed can be finalised.")
    question_set = question_set_for(assessment.question_set_version)
    consensus = consensus_of(db, assessment)
    agreed = consensus.answers if consensus is not None else {}
    scored = readiness.score_readiness(agreed, question_set)
    if not scored.complete or scored.total is None or scored.band is None:
        raise AppError(
            "answers_incomplete",
            f"Agree every answer before finalising: {len(scored.missing_question_ids)} "
            "still to agree.",
            422,
        )
    by_category = categories.readiness_categories(scored, question_set)
    ranked = priorities.readiness_priorities(scored, question_set=question_set)
    now = datetime.now(UTC)
    result = ReadinessResult(
        organisation_id=ctx.organisation_id,
        assessment_id=assessment.id,
        per_dimension={d.key: d.score for d in scored.dimensions},
        category_scores={c.key: c.score for c in by_category.categories},
        total=scored.total,
        band_key=scored.band.key,
        priorities=[{"rank": p.rank, "key": p.key, "score": p.score} for p in ranked.items],
        # Stored, not counted later: responses go when their person is deleted.
        participant_count=submitted_count(db, assessment),
        computed_at=now,
    )
    db.add(result)
    assessment.status = ReadinessStatus.FINAL
    assessment.finalised_at = now
    record(
        db,
        AuditAction.READINESS_FINALISED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="readiness_assessment",
        target_id=assessment.id,
    )
    db.commit()
    return result


def result_of(db: Session, assessment: ReadinessAssessment) -> ReadinessResult | None:
    return db.scalar(select(ReadinessResult).where(ReadinessResult.assessment_id == assessment.id))
