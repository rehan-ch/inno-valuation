"""The dashboard, the dimension drill-down and the history of the active organisation
(Phase 5; spec 4, 6, 7, 8, 9).

Readiness (out of 300, with its band) and the selected idea's IQ (out of 100) are returned
as separate values and are never combined (spec 4). Only final readiness results and
confirmed IQ assessments are shown. The client does no scoring: levels, gaps and changes
come from the engine.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.api import presenters
from app.core.deps import get_db, require_permission
from app.core.errors import AppError
from app.core.permissions import OrgContext, Permission
from app.schemas.compass import Direction
from app.schemas.insights import (
    DashboardOut,
    DimensionDetailOut,
    DimensionIqOut,
    DimensionReadinessOut,
    DimensionRefOut,
    HistoryDimensionOut,
    IdeaChoiceOut,
    IdeaHistoryOut,
    IqHeadlineOut,
    IqHistoryEntryOut,
    QuestionAnswerOut,
    ReadinessHeadlineOut,
    ReadinessHistoryEntryOut,
    ReadinessHistoryOut,
    TrendPointOut,
)
from app.schemas.readiness import BandOut, CategoryOut, ScaleOut
from app.scoring.errors import ScoringError
from app.scoring.iq import iq_maximum
from app.scoring.question_set import QUESTION_SET, Dimension
from app.scoring.targets import TargetGap
from app.scoring.trend import Change, DimensionChange
from app.services import ideas, insights, weights
from app.services.insights import IqRecord, IqStep, ReadinessRecord, ReadinessStep

router = APIRouter(tags=["dashboard"])

# Both scores need both views: the dashboard shows readiness and ideas side by side.
_view_assessments = require_permission(Permission.VIEW_ASSESSMENTS)
_view_ideas = require_permission(Permission.VIEW_IDEAS)

DimensionKey = Path(max_length=50)


def _choice(record: IqRecord) -> IdeaChoiceOut:
    return IdeaChoiceOut(
        idea_id=record.idea.id,
        title=record.idea.title,
        assessment_id=record.assessment.id,
        iq=str(record.iq),
        confirmed_at=record.confirmed_at,
    )


def _direction(change: Change[int] | None) -> Direction | None:
    return None if change is None else change.direction.value


def _readiness_headline(record: ReadinessRecord) -> ReadinessHeadlineOut:
    question_set = record.question_set
    band = next(b for b in question_set.readiness_bands if b.key == record.result.band_key)
    return ReadinessHeadlineOut(
        assessment_id=record.assessment.id,
        finalised_at=record.finalised_at,
        question_set_version=question_set.version,
        total=record.result.total,
        total_maximum=question_set.total_max,
        band=BandOut(key=band.key, name=band.name, text=band.text),
        compass=presenters.readiness_compass(record),
        priorities=presenters.readiness_priorities(record),
    )


def _iq_headline(record: IqRecord) -> IqHeadlineOut:
    return IqHeadlineOut(
        idea_id=record.idea.id,
        idea_title=record.idea.title,
        assessment_id=record.assessment.id,
        confirmed_at=record.confirmed_at,
        question_set_version=record.question_set.version,
        iq=str(record.iq),
        iq_maximum=str(iq_maximum(record.question_set)),
        vfm=presenters.vfm_out(record.assessment),
        custom_weights=weights.is_custom(record.assessment.weights_snapshot),
        compass=presenters.iq_compass(record),
        priorities=presenters.iq_priorities(record),
    )


@router.get("/dashboard", response_model=DashboardOut, status_code=status.HTTP_200_OK)
def get_dashboard(
    idea_id: uuid.UUID | None = None,
    ctx: OrgContext = Depends(_view_assessments),
    _: OrgContext = Depends(_view_ideas),
    db: Session = Depends(get_db),
) -> DashboardOut:
    """The two headline scores, kept apart: the latest final readiness result (out of 300,
    with its band) and the IQ (out of 100) of the selected idea, each with its compass and
    priorities. Without ``idea_id`` the most recently confirmed idea is selected."""
    readiness = insights.readiness_records(db, ctx)
    iq_records = insights.latest_iq_records(db, ctx)
    selected = insights.pick_idea(iq_records, idea_id)
    return DashboardOut(
        readiness=_readiness_headline(readiness[0]) if readiness else None,
        ideas=[_choice(record) for record in iq_records],
        iq=_iq_headline(selected) if selected is not None else None,
    )


# Drill-down


def _dimension(key: str) -> Dimension:
    try:
        return QUESTION_SET.dimension(key)
    except ScoringError as error:
        raise AppError("not_found", "Not found.", 404) from error


def _ref(dimension: Dimension) -> DimensionRefOut:
    return DimensionRefOut(key=dimension.key, name=dimension.name, order=dimension.order)


def _trend_point(
    assessment_id: uuid.UUID,
    at: datetime,
    score: int,
    maximum: int,
    change: DimensionChange | None,
) -> TrendPointOut:
    return TrendPointOut(
        assessment_id=assessment_id,
        at=at,
        score=score,
        maximum=maximum,
        change=change.change.change if change else None,
        direction=change.change.direction.value if change else None,
    )


def _dimension_readiness(steps: Sequence[ReadinessStep], key: str) -> DimensionReadinessOut | None:
    steps = [step for step in steps if key in step.record.scores]
    if not steps:
        return None
    record = steps[0].record
    question_set = record.question_set
    dimension = question_set.dimension(key)
    agreed = record.agreed_answers or {}
    ranks = {str(p["key"]): int(p["rank"]) for p in record.result.priorities}
    scale = question_set.readiness_scale
    return DimensionReadinessOut(
        assessment_id=record.assessment.id,
        finalised_at=record.finalised_at,
        question_set_version=question_set.version,
        score=record.scores[key],
        maximum=question_set.dimension_max,
        priority_rank=ranks.get(key),
        target=record.gaps[key].target if key in record.gaps else None,
        gap=record.gaps[key].gap if key in record.gaps else None,
        answer_scale=ScaleOut(
            min=scale.min, max=scale.max, labels={str(v): label for v, label in scale.labels}
        ),
        questions=[
            QuestionAnswerOut(
                id=q.id,
                text=q.text,
                answer=int(agreed[q.id]) if agreed.get(q.id) is not None else None,
            )
            for q in dimension.questions
        ],
        history=[
            _trend_point(
                step.record.assessment.id,
                step.record.finalised_at,
                step.record.scores[key],
                step.record.question_set.dimension_max,
                step.dimensions.get(key),
            )
            for step in steps
        ],
    )


def _dimension_iq(steps: Sequence[IqStep], key: str) -> DimensionIqOut | None:
    steps = [step for step in steps if key in step.record.rows]
    if not steps:
        return None
    record = steps[0].record
    question_set = record.question_set
    row = record.rows[key]
    score = record.scores[key]
    ranks = {str(p["key"]): int(p["rank"]) for p in (record.assessment.priorities or [])}
    return DimensionIqOut(
        idea_id=record.idea.id,
        idea_title=record.idea.title,
        assessment_id=record.assessment.id,
        confirmed_at=record.confirmed_at,
        question_set_version=question_set.version,
        score=score,
        maximum=question_set.iq_scale.max,
        level=presenters.level_out(presenters.stored_level(question_set, row.level_key, score)),
        proposed_score=row.proposed_score,
        changed=row.proposed_score is not None and row.proposed_score != score,
        rationale=[str(sentence) for sentence in (row.proposed_rationale or [])],
        note=row.note,
        priority_rank=ranks.get(key),
        target=record.gaps[key].target if key in record.gaps else None,
        gap=record.gaps[key].gap if key in record.gaps else None,
        history=[
            _trend_point(
                step.record.assessment.id,
                step.record.confirmed_at,
                step.record.scores[key],
                step.record.question_set.iq_scale.max,
                step.dimensions.get(key),
            )
            for step in steps
        ],
    )


@router.get(
    "/dashboard/dimensions/{key}",
    response_model=DimensionDetailOut,
    status_code=status.HTTP_200_OK,
)
def get_dimension(
    key: str = DimensionKey,
    idea_id: uuid.UUID | None = None,
    ctx: OrgContext = Depends(_view_assessments),
    _: OrgContext = Depends(_view_ideas),
    db: Session = Depends(get_db),
) -> DimensionDetailOut:
    """One dimension: the book's description, sub-aspects and fixed next-step text, the
    organisation's readiness score for it and the selected idea's score for it (kept
    apart), each with its target, gap and earlier scores."""
    dimension = _dimension(key)
    category = QUESTION_SET.category(dimension.category)
    index = QUESTION_SET.dimension_keys.index(dimension.key)
    readiness_steps = insights.readiness_steps(insights.readiness_records(db, ctx))
    iq_records = insights.latest_iq_records(db, ctx)
    selected = insights.pick_idea(iq_records, idea_id)
    iq_steps = (
        insights.iq_steps(insights.idea_iq_records(db, ctx, selected.idea))
        if selected is not None
        else []
    )
    return DimensionDetailOut(
        key=dimension.key,
        name=dimension.name,
        order=dimension.order,
        category=CategoryOut(key=category.key, name=category.name, order=category.order),
        description=dimension.description,
        sub_aspects=list(dimension.sub_aspects),
        next_steps=dimension.next_steps,
        previous=_ref(QUESTION_SET.dimensions[index - 1]) if index > 0 else None,
        next=(
            _ref(QUESTION_SET.dimensions[index + 1])
            if index + 1 < len(QUESTION_SET.dimensions)
            else None
        ),
        readiness=_dimension_readiness(readiness_steps, dimension.key),
        ideas=[_choice(record) for record in iq_records],
        iq=_dimension_iq(iq_steps, dimension.key),
    )


# History (spec 9)


def _history_dimensions(
    question_set_dimensions: Sequence[Dimension],
    scores: dict[str, int],
    maximum: int,
    changes: Mapping[str, DimensionChange],
    gaps: Mapping[str, TargetGap],
) -> list[HistoryDimensionOut]:
    rows = []
    for d in question_set_dimensions:
        change = changes.get(d.key)
        gap = gaps.get(d.key)
        rows.append(
            HistoryDimensionOut(
                key=d.key,
                name=d.name,
                order=d.order,
                score=scores[d.key],
                maximum=maximum,
                change=change.change.change if change else None,
                direction=change.change.direction.value if change else None,
                target=gap.target if gap else None,
                gap=gap.gap if gap else None,
            )
        )
    return rows


@router.get(
    "/history/readiness", response_model=ReadinessHistoryOut, status_code=status.HTTP_200_OK
)
def get_readiness_history(
    ctx: OrgContext = Depends(_view_assessments), db: Session = Depends(get_db)
) -> ReadinessHistoryOut:
    """Every final readiness result, newest first, each compared with the one before it on
    the same question set version: change on the total and per dimension (spec 9)."""
    entries = []
    for step in insights.readiness_steps(insights.readiness_records(db, ctx)):
        record = step.record
        question_set = record.question_set
        band = next(b for b in question_set.readiness_bands if b.key == record.result.band_key)
        entries.append(
            ReadinessHistoryEntryOut(
                assessment_id=record.assessment.id,
                finalised_at=record.finalised_at,
                question_set_version=question_set.version,
                total=record.result.total,
                total_maximum=question_set.total_max,
                band_name=band.name,
                compared_with=step.compared_with.assessment.id if step.compared_with else None,
                total_change=step.total.change if step.total else None,
                total_direction=_direction(step.total),
                dimensions=_history_dimensions(
                    question_set.dimensions,
                    record.scores,
                    question_set.dimension_max,
                    step.dimensions,
                    record.gaps,
                ),
            )
        )
    return ReadinessHistoryOut(entries=entries)


@router.get(
    "/history/ideas/{idea_id}", response_model=IdeaHistoryOut, status_code=status.HTTP_200_OK
)
def get_idea_history(
    idea_id: uuid.UUID,
    ctx: OrgContext = Depends(_view_ideas),
    db: Session = Depends(get_db),
) -> IdeaHistoryOut:
    """Every confirmed IQ assessment of one idea, newest first, each compared with the one
    before it on the same question set version: change in IQ, Value for Money (same
    currency only) and per dimension (spec 9)."""
    idea = ideas.get_idea(db, ctx, idea_id)
    entries = []
    for step in insights.iq_steps(insights.idea_iq_records(db, ctx, idea)):
        record = step.record
        question_set = record.question_set
        entries.append(
            IqHistoryEntryOut(
                assessment_id=record.assessment.id,
                confirmed_at=record.confirmed_at,
                question_set_version=question_set.version,
                iq=str(record.iq),
                iq_maximum=str(iq_maximum(question_set)),
                compared_with=step.compared_with.assessment.id if step.compared_with else None,
                iq_change=str(step.iq.change) if step.iq else None,
                iq_direction=step.iq.direction.value if step.iq else None,
                vfm=presenters.vfm_out(record.assessment),
                vfm_change=str(step.vfm.change) if step.vfm else None,
                vfm_direction=step.vfm.direction.value if step.vfm else None,
                dimensions=_history_dimensions(
                    question_set.dimensions,
                    record.scores,
                    question_set.iq_scale.max,
                    step.dimensions,
                    record.gaps,
                ),
            )
        )
    return IdeaHistoryOut(idea_id=idea.id, idea_title=idea.title, entries=entries)
