"""Readiness assessments of the active organisation (spec 2, Amy Q5)."""

import uuid
from typing import Final

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.ai.client import OFFLINE_MODEL
from app.ai.touchpoints import explain_question as explain_question_touchpoint
from app.core.deps import get_db, require_permission
from app.core.errors import AppError
from app.core.permissions import OrgContext, Permission, has_permission
from app.models import AiRun, ReadinessAssessment, ReadinessResponse
from app.models.enums import AiRunStatus, ReadinessStatus
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
    ExplanationOut,
    ExplanationStatus,
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
from app.services import explanations, readiness

router = APIRouter(prefix="/readiness", tags=["readiness"])

# PROVISIONAL (display only): the result calls up to this many top-scoring dimensions
# strengths. Amy has set the priorities list (lowest 5); she has not set strengths. A
# strength must score above every priority, so no dimension is ever both.
STRENGTH_COUNT: Final = 3


def _answers_by_role(ctx: OrgContext) -> bool:
    """The caller's role answers assessments. Unlike ``ctx.can``, this ignores an archived
    organisation, so people still see their own past answers there."""
    return has_permission(ctx.role, Permission.ANSWER_ASSESSMENT)


def _my_status(ctx: OrgContext, own: ReadinessResponse | None) -> MyStatus | None:
    if not _answers_by_role(ctx):
        return None
    if own is None or not own.answers:
        return "not_started"
    return "submitted" if own.submitted_at else "in_progress"


def _summary(
    ctx: OrgContext, assessment: ReadinessAssessment, overview: readiness.Overview
) -> AssessmentSummaryOut:
    band_name = None
    if overview.result is not None:
        bands = question_set_for(assessment.question_set_version).readiness_bands
        band_name = next(b.name for b in bands if b.key == overview.result.band_key)
    return AssessmentSummaryOut(
        id=assessment.id,
        status=assessment.status,
        question_set_version=assessment.question_set_version,
        created_at=assessment.created_at,
        started_at=assessment.started_at,
        finalised_at=assessment.finalised_at,
        created_by_name=overview.creator_name,
        submitted_count=overview.submitted_count,
        my_status=_my_status(ctx, overview.own),
        total=overview.result.total if overview.result else None,
        band_name=band_name,
    )


def _detail(db: Session, ctx: OrgContext, assessment: ReadinessAssessment) -> AssessmentOut:
    overview = readiness.overviews(db, ctx.user.id, [assessment])[assessment.id]
    question_set = question_set_for(assessment.question_set_version)
    answers_by_role = _answers_by_role(ctx)
    own = overview.own if answers_by_role else None
    can_manage = ctx.can(Permission.MANAGE_ASSESSMENTS)
    participants = None
    if can_manage:
        participants = [
            ParticipantOut(
                user_id=r.user_id,
                name=r.user.name,
                answered=len(r.answers),
                submitted_at=r.submitted_at,
            )
            for r in readiness.responses(db, assessment)
        ]
    return AssessmentOut(
        **_summary(ctx, assessment, overview).model_dump(),
        my_answers=dict(own.answers) if own else ({} if answers_by_role else None),
        my_submitted_at=own.submitted_at if own else None,
        question_count=len(question_set.all_question_ids()),
        # May answer now: an answering role in an organisation that is not archived.
        can_answer=ctx.can(Permission.ANSWER_ASSESSMENT),
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
    assessments = readiness.list_assessments(db, ctx)
    found = readiness.overviews(db, ctx.user.id, assessments)
    return [_summary(ctx, a, found[a.id]) for a in assessments]


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
    submitted = [r for r in readiness.responses(db, assessment) if r.submitted_at is not None]
    table = readiness.consensus_table(db, assessment, submitted)
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
                answers=[
                    PersonAnswerOut(user_id=p.user_id, name=p.name, answer=p.answer)
                    for p in row.answers
                ],
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
    highest_priority = max((int(p["score"]) for p in result.priorities), default=-1)
    strongest = [
        d
        for d in sorted(dimensions, key=lambda d: (-d.score, d.order))
        if d.score > highest_priority
    ][:STRENGTH_COUNT]
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
        submitted_count=result.participant_count,
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


_EXPLANATION_STATUS: Final[dict[AiRunStatus, ExplanationStatus]] = {
    AiRunStatus.QUEUED: "pending",
    AiRunStatus.RUNNING: "pending",
    AiRunStatus.SUCCEEDED: "ready",
    AiRunStatus.FAILED: "failed",
}

QuestionId = Path(max_length=100)


def _version(version: int | None) -> int:
    """The question set version asked about; the current one when not given."""
    return QUESTION_SET.version if version is None else version


def _explanation_out(run: AiRun) -> ExplanationOut:
    version, question_id = explain_question_touchpoint.parse_subject(run.subject_id)
    dimension = question_set_for(version).dimension_of_question(question_id)
    output = run.response_json if run.status is AiRunStatus.SUCCEEDED else None
    return ExplanationOut(
        question_id=question_id,
        question_set_version=version,
        dimension_key=dimension.key,
        dimension_name=dimension.name,
        status=_EXPLANATION_STATUS[run.status],
        explanation=list(output["explanation"]) if output else None,
        example=str(output["example"]) if output else None,
        sample=run.response_model == OFFLINE_MODEL,
        created_at=run.created_at,
    )


@router.post(
    "/questions/{question_id}/explanation",
    response_model=ExplanationOut,
    status_code=status.HTTP_200_OK,
)
def explain_question(
    question_id: str = QuestionId,
    version: int | None = None,
    ctx: OrgContext = Depends(require_permission(Permission.ANSWER_ASSESSMENT)),
    db: Session = Depends(get_db),
) -> ExplanationOut:
    """Answers "What does this mean?" on a question: the organisation's saved AI explanation,
    or a new one on its way (status "pending"; poll the GET until "ready" or "failed")."""
    run = explanations.request(db, ctx, _version(version), question_id)
    return _explanation_out(run)


@router.get(
    "/questions/{question_id}/explanation",
    response_model=ExplanationOut,
    status_code=status.HTTP_200_OK,
)
def get_explanation(
    question_id: str = QuestionId,
    version: int | None = None,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> ExplanationOut:
    """The latest explanation of a question in this organisation; 404 if nobody asked yet."""
    run = explanations.latest(db, ctx, _version(version), question_id)
    if run is None:
        raise AppError("not_found", "Nobody has asked about this question yet.", 404)
    return _explanation_out(run)
