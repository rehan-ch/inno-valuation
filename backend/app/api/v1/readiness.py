"""Readiness assessments of the active organisation (spec 2, Amy Q5)."""

import uuid
from typing import Final

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.errors import AppError
from app.core.permissions import OrgContext, Permission
from app.models import ReadinessAssessment, User
from app.models.enums import ReadinessStatus
from app.schemas.readiness import (
    AnswersIn,
    AssessmentOut,
    AssessmentSummaryOut,
    BandOut,
    CategoryOut,
    CategoryScoreOut,
    ConsensusIn,
    ConsensusOut,
    DimensionOut,
    DimensionScoreOut,
    MyStatus,
    ParticipantOut,
    PersonAnswerOut,
    PriorityOut,
    QuestionConsensusOut,
    QuestionOut,
    QuestionSetOut,
    ResultOut,
    ScaleOut,
)
from app.scoring.errors import ScoringError
from app.scoring.question_set import QUESTION_SET, question_set_for
from app.services import readiness

router = APIRouter(prefix="/readiness", tags=["readiness"])

# PROVISIONAL (display only): how many top-scoring dimensions the result calls strengths.
# Amy has set the priorities list (lowest 5); she has not set a count for strengths.
STRENGTH_COUNT: Final = 3


def _my_status(db: Session, ctx: OrgContext, assessment: ReadinessAssessment) -> MyStatus | None:
    if not ctx.can(Permission.ANSWER_ASSESSMENT):
        return None
    response = readiness.own_response(db, assessment, ctx.user.id)
    if response is None or not response.answers:
        return "not_started"
    return "submitted" if response.submitted_at else "in_progress"


def _summary(db: Session, ctx: OrgContext, assessment: ReadinessAssessment) -> AssessmentSummaryOut:
    result = readiness.result_of(db, assessment)
    band_name = None
    if result is not None:
        bands = question_set_for(assessment.question_set_version).readiness_bands
        band_name = next(b.name for b in bands if b.key == result.band_key)
    creator = None
    if assessment.created_by_user_id is not None:
        creator_user = db.get(User, assessment.created_by_user_id)
        creator = creator_user.name if creator_user else None
    return AssessmentSummaryOut(
        id=assessment.id,
        status=assessment.status,
        question_set_version=assessment.question_set_version,
        created_at=assessment.created_at,
        started_at=assessment.started_at,
        finalised_at=assessment.finalised_at,
        created_by_name=creator,
        submitted_count=readiness.submitted_count(db, assessment),
        my_status=_my_status(db, ctx, assessment),
        total=result.total if result else None,
        band_name=band_name,
    )


def _detail(db: Session, ctx: OrgContext, assessment: ReadinessAssessment) -> AssessmentOut:
    summary = _summary(db, ctx, assessment)
    question_set = question_set_for(assessment.question_set_version)
    can_answer = ctx.can(Permission.ANSWER_ASSESSMENT)
    can_manage = ctx.can(Permission.MANAGE_ASSESSMENTS)
    own = readiness.own_response(db, assessment, ctx.user.id) if can_answer else None
    participants = None
    if can_manage:
        participants = [
            ParticipantOut(name=r.user.name, answered=len(r.answers), submitted_at=r.submitted_at)
            for r in readiness.responses(db, assessment)
        ]
    return AssessmentOut(
        **summary.model_dump(),
        my_answers=dict(own.answers) if own else ({} if can_answer else None),
        my_submitted_at=own.submitted_at if own else None,
        question_count=len(question_set.all_question_ids()),
        can_answer=can_answer,
        can_manage=can_manage,
        participants=participants,
    )


@router.get("/question-set", response_model=QuestionSetOut, status_code=status.HTTP_200_OK)
def get_question_set(
    version: int | None = None,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
) -> QuestionSetOut:
    """The 60 readiness questions, verbatim from the book, grouped by dimension in book order."""
    try:
        question_set = question_set_for(version) if version is not None else QUESTION_SET
    except ScoringError as error:  # unknown version
        raise AppError("not_found", "Not found.", 404) from error
    return QuestionSetOut(
        version=question_set.version,
        scale=ScaleOut(
            min=question_set.readiness_scale.min,
            max=question_set.readiness_scale.max,
            labels={str(value): label for value, label in question_set.readiness_scale.labels},
        ),
        categories=[
            CategoryOut(key=c.key, name=c.name, order=c.order) for c in question_set.categories
        ],
        dimensions=[
            DimensionOut(
                key=d.key,
                name=d.name,
                order=d.order,
                category=d.category,
                description=d.description,
                questions=[QuestionOut(id=q.id, text=q.text) for q in d.questions],
            )
            for d in question_set.dimensions
        ],
    )


@router.get(
    "/assessments", response_model=list[AssessmentSummaryOut], status_code=status.HTTP_200_OK
)
def list_assessments(
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> list[AssessmentSummaryOut]:
    return [_summary(db, ctx, a) for a in readiness.list_assessments(db, ctx)]


@router.post("/assessments", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
def start_assessment(
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> AssessmentOut:
    return _detail(db, ctx, readiness.start_assessment(db, ctx))


@router.get(
    "/assessments/{assessment_id}", response_model=AssessmentOut, status_code=status.HTTP_200_OK
)
def get_assessment(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> AssessmentOut:
    return _detail(db, ctx, readiness.get_assessment(db, ctx, assessment_id))


@router.patch(
    "/assessments/{assessment_id}/my-answers",
    response_model=AssessmentOut,
    status_code=status.HTTP_200_OK,
)
def save_my_answers(
    assessment_id: uuid.UUID,
    body: AnswersIn,
    ctx: OrgContext = Depends(require_permission(Permission.ANSWER_ASSESSMENT)),
    db: Session = Depends(get_db),
) -> AssessmentOut:
    """Autosave: merge these answers into the caller's own; null clears one."""
    readiness.save_answers(db, ctx, assessment_id, body.answers)
    return _detail(db, ctx, readiness.get_assessment(db, ctx, assessment_id))


@router.post(
    "/assessments/{assessment_id}/my-answers/submit",
    response_model=AssessmentOut,
    status_code=status.HTTP_200_OK,
)
def submit_my_answers(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.ANSWER_ASSESSMENT)),
    db: Session = Depends(get_db),
) -> AssessmentOut:
    readiness.submit_answers(db, ctx, assessment_id)
    return _detail(db, ctx, readiness.get_assessment(db, ctx, assessment_id))


def _consensus_out(db: Session, assessment: ReadinessAssessment) -> ConsensusOut:
    table = readiness.consensus_table(db, assessment)
    submitted = [r for r in readiness.responses(db, assessment) if r.submitted_at is not None]
    return ConsensusOut(
        assessment_id=assessment.id,
        status=assessment.status,
        participants=[r.user.name for r in submitted],
        agreed_count=sum(1 for row in table if row.agreed is not None),
        question_count=len(table),
        questions=[
            QuestionConsensusOut(
                question_id=row.question_id,
                dimension_key=row.dimension_key,
                answers=[PersonAnswerOut(name=p.name, answer=p.answer) for p in row.answers],
                mean=str(row.mean) if row.mean is not None else None,
                spread=row.spread,
                wide_spread=row.wide_spread,
                agreed=row.agreed,
                note=row.note,
            )
            for row in table
        ],
    )


@router.post(
    "/assessments/{assessment_id}/consensus/begin",
    response_model=ConsensusOut,
    status_code=status.HTTP_200_OK,
)
def begin_consensus(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> ConsensusOut:
    return _consensus_out(db, readiness.begin_consensus(db, ctx, assessment_id))


@router.get(
    "/assessments/{assessment_id}/consensus",
    response_model=ConsensusOut,
    status_code=status.HTTP_200_OK,
)
def get_consensus(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> ConsensusOut:
    """Everyone's submitted answers, the mean and spread, and the agreed answers so far.
    The facilitator's view; individual answers are never shown to anyone else."""
    assessment = readiness.get_assessment(db, ctx, assessment_id)
    if assessment.status is ReadinessStatus.COLLECTING:
        raise AppError("wrong_status", "Agreeing the answers has not started.", 409)
    return _consensus_out(db, assessment)


@router.patch(
    "/assessments/{assessment_id}/consensus",
    response_model=ConsensusOut,
    status_code=status.HTTP_200_OK,
)
def save_consensus(
    assessment_id: uuid.UUID,
    body: ConsensusIn,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> ConsensusOut:
    readiness.save_consensus(db, ctx, assessment_id, answers=body.answers, notes=body.notes)
    return _consensus_out(db, readiness.get_assessment(db, ctx, assessment_id))


@router.post(
    "/assessments/{assessment_id}/finalise",
    response_model=ResultOut,
    status_code=status.HTTP_200_OK,
)
def finalise(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> ResultOut:
    readiness.finalise(db, ctx, assessment_id)
    return _result_out(db, readiness.get_assessment(db, ctx, assessment_id))


def _result_out(db: Session, assessment: ReadinessAssessment) -> ResultOut:
    result = readiness.result_of(db, assessment)
    if result is None or assessment.finalised_at is None:
        raise AppError("not_found", "This assessment has no result yet.", 404)
    question_set = question_set_for(assessment.question_set_version)
    band = next(b for b in question_set.readiness_bands if b.key == result.band_key)
    dimension_max = question_set.dimension_max
    dimensions = [
        DimensionScoreOut(
            key=d.key,
            name=d.name,
            order=d.order,
            category=d.category,
            score=int(result.per_dimension[d.key]),
            maximum=dimension_max,
        )
        for d in question_set.dimensions
    ]
    strongest = sorted(dimensions, key=lambda d: (-d.score, d.order))[:STRENGTH_COUNT]
    return ResultOut(
        assessment_id=assessment.id,
        question_set_version=assessment.question_set_version,
        total=result.total,
        total_maximum=question_set.total_max,
        band=BandOut(key=band.key, name=band.name, text=band.text),
        dimensions=dimensions,
        categories=[
            CategoryScoreOut(
                key=c.key,
                name=c.name,
                score=int(result.category_scores[c.key]),
                maximum=len(question_set.dimensions_in_category(c.key)) * dimension_max,
            )
            for c in question_set.categories
        ],
        priorities=[
            PriorityOut(
                rank=int(p["rank"]),
                key=str(p["key"]),
                name=question_set.dimension(str(p["key"])).name,
                score=int(p["score"]),
                maximum=dimension_max,
                next_steps=question_set.dimension(str(p["key"])).next_steps,
            )
            for p in result.priorities
        ],
        strengths=strongest,
        submitted_count=readiness.submitted_count(db, assessment),
        finalised_at=assessment.finalised_at,
    )


@router.get(
    "/assessments/{assessment_id}/result",
    response_model=ResultOut,
    status_code=status.HTTP_200_OK,
)
def get_result(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> ResultOut:
    """The final result: total out of 300 and its band in the book's words, the 12 dimension
    scores, category totals, priorities with the book's next steps, and strengths."""
    return _result_out(db, readiness.get_assessment(db, ctx, assessment_id))
