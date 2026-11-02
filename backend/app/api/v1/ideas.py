"""Ideas of the active organisation and their IQ assessments (spec 3, 5, 7; Amy Q1, Q7)."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.currencies import to_major_units
from app.core.deps import get_db, require_permission
from app.core.permissions import OrgContext, Permission
from app.models import AiRun, Idea, IqAssessment
from app.models.enums import IqAssessmentStatus
from app.schemas.ideas import (
    AssessmentBriefOut,
    DimensionReviewOut,
    IdeaCreateIn,
    IdeaOut,
    IdeaSummaryOut,
    IdeaUpdateIn,
    IqAssessmentOut,
    IqCategoryOut,
    IqPriorityOut,
    IqScaleOut,
    LevelOut,
    ReviewIn,
    VfmOut,
)
from app.scoring.iq import iq_maximum
from app.scoring.question_set import IqLevel, QuestionSet
from app.services import ideas

router = APIRouter(prefix="/ideas", tags=["ideas"])


def _money(minor: int | None, currency: str | None) -> str | None:
    if minor is None or currency is None:
        return None
    return str(to_major_units(minor, currency))


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _brief(db: Session, assessment: IqAssessment, run: AiRun | None) -> AssessmentBriefOut:
    return AssessmentBriefOut(
        id=assessment.id,
        status=assessment.status,
        proposal_status=ideas.proposal_status(db, assessment, run),
        sample=ideas.is_sample(run),
        iq=_text(assessment.iq),
        vfm_per_point=_text(assessment.vfm_per_point),
        currency=assessment.currency,
        requested_at=assessment.created_at,
        confirmed_at=assessment.confirmed_at,
    )


def _summary(db: Session, idea: Idea, overview: ideas.Overview) -> IdeaSummaryOut:
    return IdeaSummaryOut(
        id=idea.id,
        title=idea.title,
        stage=idea.stage,
        status=idea.status,
        archived=idea.archived_at is not None,
        currency=idea.currency,
        investment=_money(idea.investment_minor, idea.currency),
        expected_value=_money(idea.expected_value_minor, idea.currency),
        created_by_name=overview.creator_name,
        created_at=idea.created_at,
        updated_at=idea.updated_at,
        latest_assessment=(
            _brief(db, overview.latest, overview.run) if overview.latest is not None else None
        ),
    )


def _detail(db: Session, ctx: OrgContext, idea: Idea) -> IdeaOut:
    overview = ideas.overviews(db, [idea])[idea.id]
    history = ideas.assessments_of(db, idea)
    if ctx.is_consultant:
        history = [a for a in history if a.status is IqAssessmentStatus.CONFIRMED]
    return IdeaOut(
        **_summary(db, idea, overview).model_dump(),
        summary=idea.summary,
        problem=idea.problem,
        target_market=idea.target_market,
        uniqueness=idea.uniqueness,
        team=idea.team,
        risks=idea.risks,
        can_change=ideas.may_change(ctx, idea),
        can_archive=ctx.can(Permission.MANAGE_IDEAS),
        assessments=[_brief(db, a, ideas.run_of(db, a)) for a in history],
    )


@router.get("", response_model=list[IdeaSummaryOut], status_code=status.HTTP_200_OK)
def list_ideas(
    include_archived: bool = False,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_IDEAS)),
    db: Session = Depends(get_db),
) -> list[IdeaSummaryOut]:
    """The organisation's ideas, newest first, each with its latest assessment's IQ and
    Value for Money. Compare and sort on the client: every number is already here."""
    found = ideas.list_ideas(db, ctx, include_archived=include_archived)
    overviews = ideas.overviews(db, found)
    return [_summary(db, idea, overviews[idea.id]) for idea in found]


@router.post("", response_model=IdeaOut, status_code=status.HTTP_201_CREATED)
def create_idea(
    body: IdeaCreateIn,
    ctx: OrgContext = Depends(require_permission(Permission.CREATE_IDEAS)),
    db: Session = Depends(get_db),
) -> IdeaOut:
    return _detail(db, ctx, ideas.create_idea(db, ctx, body.values()))


@router.get("/{idea_id}", response_model=IdeaOut, status_code=status.HTTP_200_OK)
def get_idea(
    idea_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_IDEAS)),
    db: Session = Depends(get_db),
) -> IdeaOut:
    return _detail(db, ctx, ideas.get_idea(db, ctx, idea_id))


@router.patch("/{idea_id}", response_model=IdeaOut, status_code=status.HTTP_200_OK)
def update_idea(
    idea_id: uuid.UUID,
    body: IdeaUpdateIn,
    ctx: OrgContext = Depends(require_permission(Permission.CREATE_IDEAS)),
    db: Session = Depends(get_db),
) -> IdeaOut:
    """Change an idea. Its creator may; so may an owner or admin."""
    return _detail(db, ctx, ideas.update_idea(db, ctx, idea_id, body.changes()))


@router.post("/{idea_id}/archive", response_model=IdeaOut, status_code=status.HTTP_200_OK)
def archive_idea(
    idea_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_IDEAS)),
    db: Session = Depends(get_db),
) -> IdeaOut:
    return _detail(db, ctx, ideas.archive_idea(db, ctx, idea_id))


@router.post("/{idea_id}/restore", response_model=IdeaOut, status_code=status.HTTP_200_OK)
def restore_idea(
    idea_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_IDEAS)),
    db: Session = Depends(get_db),
) -> IdeaOut:
    return _detail(db, ctx, ideas.restore_idea(db, ctx, idea_id))


def _level_out(level: IqLevel) -> LevelOut:
    return LevelOut(key=level.key, name=level.name, min=level.min, max=level.max, text=level.text)


def _vfm_out(assessment: IqAssessment) -> VfmOut | None:
    if assessment.status is not IqAssessmentStatus.CONFIRMED or assessment.currency is None:
        return None
    reason = None
    if assessment.investment_minor is None:
        reason = "No investment was given for this idea."
    elif assessment.vfm_per_point is None:
        reason = "Value for Money cannot be worked out for this IQ."
    return VfmOut(
        investment=_money(assessment.investment_minor, assessment.currency),
        currency=assessment.currency,
        per_point=_text(assessment.vfm_per_point),
        not_calculable_reason=reason,
    )


def _assessment_out(
    db: Session, ctx: OrgContext, idea: Idea, assessment: IqAssessment
) -> IqAssessmentOut:
    question_set: QuestionSet = ideas.question_set_of(assessment)
    run = ideas.run_of(db, assessment)
    proposal = ideas.proposal_status(db, assessment, run)
    rows = {row.dimension_key: row for row in ideas.load_scores(db, assessment)}
    levels = {level.key: level for level in question_set.iq_levels}
    dimensions = []
    for dimension in question_set.dimensions:
        row = rows.get(dimension.key)
        level = levels.get(row.level_key) if row is not None and row.level_key else None
        dimensions.append(
            DimensionReviewOut(
                key=dimension.key,
                name=dimension.name,
                order=dimension.order,
                category=dimension.category,
                description=dimension.description,
                proposed_score=row.proposed_score if row else None,
                proposed_rationale=(
                    [str(s) for s in row.proposed_rationale]
                    if row is not None and row.proposed_rationale is not None
                    else None
                ),
                proposed_confidence=_text(row.proposed_confidence) if row else None,
                final_score=row.final_score if row else None,
                level=_level_out(level) if level is not None else None,
                note=row.note if row else None,
                changed=(
                    row is not None
                    and row.final_score is not None
                    and row.final_score != row.proposed_score
                ),
            )
        )
    names = ideas.user_names(
        db,
        {
            user_id
            for user_id in (assessment.requested_by_user_id, assessment.confirmed_by_user_id)
            if user_id is not None
        },
    )
    category_scores = assessment.category_scores or {}
    return IqAssessmentOut(
        id=assessment.id,
        idea_id=idea.id,
        idea_title=idea.title,
        status=assessment.status,
        proposal_status=proposal,
        sample=ideas.is_sample(run),
        question_set_version=assessment.question_set_version,
        scale=IqScaleOut(min=question_set.iq_scale.min, max=question_set.iq_scale.max),
        levels=[_level_out(level) for level in question_set.iq_levels],
        dimensions=dimensions,
        missing_information=ideas.missing_information(run),
        iq=_text(assessment.iq),
        iq_maximum=str(iq_maximum(question_set)),
        categories=[
            IqCategoryOut(
                key=c.key,
                name=c.name,
                score=str(category_scores[c.key]) if c.key in category_scores else None,
                maximum=str(iq_maximum(question_set)),
            )
            for c in question_set.categories
        ],
        priorities=[
            IqPriorityOut(
                rank=int(p["rank"]),
                key=str(p["key"]),
                name=question_set.dimension(str(p["key"])).name,
                score=int(p["score"]),
                level_name=next(
                    lv.name for lv in question_set.iq_levels if lv.min <= int(p["score"]) <= lv.max
                ),
                next_steps=question_set.dimension(str(p["key"])).next_steps,
            )
            for p in (assessment.priorities or [])
        ],
        vfm=_vfm_out(assessment),
        can_review=(
            assessment.status is IqAssessmentStatus.PROPOSED and ideas.may_change(ctx, idea)
        ),
        requested_at=assessment.created_at,
        requested_by_name=(
            names.get(assessment.requested_by_user_id) if assessment.requested_by_user_id else None
        ),
        confirmed_at=assessment.confirmed_at,
        confirmed_by_name=(
            names.get(assessment.confirmed_by_user_id) if assessment.confirmed_by_user_id else None
        ),
    )


@router.post(
    "/{idea_id}/assessments", response_model=IqAssessmentOut, status_code=status.HTTP_201_CREATED
)
def request_assessment(
    idea_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.CREATE_IDEAS)),
    db: Session = Depends(get_db),
) -> IqAssessmentOut:
    """Send the idea for scoring. The AI proposes a 1 to 10 score per dimension in the
    background (poll the GET until ``proposal_status`` is "ready" or "failed"); the owner
    then confirms or changes each one (Amy Q1). Scoring again keeps the earlier confirmed
    assessments for history."""
    assessment = ideas.request_assessment(db, ctx, idea_id)
    return _assessment_out(db, ctx, ideas.get_idea(db, ctx, idea_id), assessment)


@router.get(
    "/{idea_id}/assessments/{assessment_id}",
    response_model=IqAssessmentOut,
    status_code=status.HTTP_200_OK,
)
def get_assessment(
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_IDEAS)),
    db: Session = Depends(get_db),
) -> IqAssessmentOut:
    """The proposal beside the owner's review and, once confirmed, the result: IQ out of 100,
    levels, category scores, priorities with the book's next steps, Value for Money."""
    idea = ideas.get_idea(db, ctx, idea_id)
    return _assessment_out(db, ctx, idea, ideas.get_assessment(db, ctx, idea, assessment_id))


@router.patch(
    "/{idea_id}/assessments/{assessment_id}/review",
    response_model=IqAssessmentOut,
    status_code=status.HTTP_200_OK,
)
def save_review(
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    body: ReviewIn,
    ctx: OrgContext = Depends(require_permission(Permission.CREATE_IDEAS)),
    db: Session = Depends(get_db),
) -> IqAssessmentOut:
    """Autosave of the owner's review: changed scores (null puts the proposal back) and notes."""
    ideas.save_review(db, ctx, idea_id, assessment_id, scores=body.scores, notes=body.notes)
    idea = ideas.get_idea(db, ctx, idea_id)
    return _assessment_out(db, ctx, idea, ideas.get_assessment(db, ctx, idea, assessment_id))


@router.post(
    "/{idea_id}/assessments/{assessment_id}/confirm",
    response_model=IqAssessmentOut,
    status_code=status.HTTP_200_OK,
)
def confirm_assessment(
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.CREATE_IDEAS)),
    db: Session = Depends(get_db),
) -> IqAssessmentOut:
    """Make the scores final. The engine computes the IQ, levels, category scores,
    priorities and Value for Money once; nothing about the assessment changes afterwards."""
    ideas.confirm(db, ctx, idea_id, assessment_id)
    idea = ideas.get_idea(db, ctx, idea_id)
    return _assessment_out(db, ctx, idea, ideas.get_assessment(db, ctx, idea, assessment_id))
