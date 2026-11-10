"""Response builders shared by more than one router: money, levels, Value for Money, the
compass and priority lists. They copy what the engine wrote; they compute nothing."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from app.core.currencies import to_major_units
from app.models import IqAssessment
from app.models.enums import IqAssessmentStatus
from app.schemas.compass import (
    CompassCategoryOut,
    CompassLevelOut,
    CompassOut,
    CompassSegmentOut,
    SegmentLevelOut,
)
from app.schemas.ideas import LevelOut, VfmOut
from app.schemas.insights import PriorityItemOut
from app.scoring.categories import readiness_category_maximum
from app.scoring.iq import iq_level, iq_maximum
from app.scoring.question_set import IqLevel, QuestionSet
from app.services.insights import IqRecord, ReadinessRecord


def money(minor: int | None, currency: str | None) -> str | None:
    if minor is None or currency is None:
        return None
    return str(to_major_units(minor, currency))


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def level_out(level: IqLevel) -> LevelOut:
    return LevelOut(key=level.key, name=level.name, min=level.min, max=level.max, text=level.text)


def vfm_out(assessment: IqAssessment) -> VfmOut | None:
    if assessment.status is not IqAssessmentStatus.CONFIRMED or assessment.currency is None:
        return None
    reason = None
    if assessment.investment_minor is None:
        reason = "No investment was given for this idea."
    elif assessment.vfm_per_point is None:
        reason = "Value for Money cannot be worked out for this IQ."
    return VfmOut(
        investment=money(assessment.investment_minor, assessment.currency),
        currency=assessment.currency,
        per_point=decimal_text(assessment.vfm_per_point),
        not_calculable_reason=reason,
    )


def _ranks(priorities: Sequence[Any] | None) -> dict[str, int]:
    return {str(p["key"]): int(p["rank"]) for p in (priorities or [])}


def _levels_low_to_high(question_set: QuestionSet) -> list[IqLevel]:
    return sorted(question_set.iq_levels, key=lambda level: level.min)


def stored_level(question_set: QuestionSet, level_key: str | None, score: int) -> IqLevel:
    """The level the engine stored at confirmation (spec 3.1); the engine's level of the
    score when the stored key is missing."""
    for level in question_set.iq_levels:
        if level.key == level_key:
            return level
    return iq_level(score, question_set)


def readiness_compass(record: ReadinessRecord) -> CompassOut:
    """The compass of one final readiness result: 12 dimension scores in book order, the
    category totals with their maximums (spec 2.6), and no per-dimension label (Q4)."""
    question_set = record.question_set
    scores = record.scores
    ranks = _ranks(record.result.priorities)
    category_scores: Mapping[str, Any] = record.result.category_scores
    return CompassOut(
        scale="readiness",
        question_set_version=question_set.version,
        minimum=question_set.dimension_min,
        maximum=question_set.dimension_max,
        segments=[
            CompassSegmentOut(
                key=d.key,
                name=d.name,
                order=d.order,
                category=d.category,
                score=scores[d.key],
                maximum=question_set.dimension_max,
                level=None,
                priority_rank=ranks.get(d.key),
                target=record.gaps[d.key].target if d.key in record.gaps else None,
                gap=record.gaps[d.key].gap if d.key in record.gaps else None,
            )
            for d in question_set.dimensions
        ],
        categories=[
            CompassCategoryOut(
                key=c.key,
                name=c.name,
                order=c.order,
                score=str(int(category_scores[c.key])),
                maximum=str(readiness_category_maximum(c.key, question_set)),
                dimension_keys=[d.key for d in question_set.dimensions_in_category(c.key)],
            )
            for c in question_set.categories
            if c.key in category_scores
        ],
        levels=[],
    )


def iq_compass(record: IqRecord) -> CompassOut:
    """The compass of one confirmed IQ assessment: 12 final scores in book order with the
    book's level each (spec 3.1), and the category IQs (spec 3.6)."""
    question_set = record.question_set
    levels = _levels_low_to_high(question_set)
    place = {level.key: index + 1 for index, level in enumerate(levels)}
    scores = record.scores
    ranks = _ranks(record.assessment.priorities)
    category_scores: Mapping[str, Any] = record.assessment.category_scores or {}
    segments = []
    for d in question_set.dimensions:
        level = stored_level(question_set, record.rows[d.key].level_key, scores[d.key])
        segments.append(
            CompassSegmentOut(
                key=d.key,
                name=d.name,
                order=d.order,
                category=d.category,
                score=scores[d.key],
                maximum=question_set.iq_scale.max,
                level=SegmentLevelOut(key=level.key, name=level.name, order=place[level.key]),
                priority_rank=ranks.get(d.key),
                target=record.gaps[d.key].target if d.key in record.gaps else None,
                gap=record.gaps[d.key].gap if d.key in record.gaps else None,
            )
        )
    return CompassOut(
        scale="iq",
        question_set_version=question_set.version,
        minimum=question_set.iq_scale.min,
        maximum=question_set.iq_scale.max,
        segments=segments,
        categories=[
            CompassCategoryOut(
                key=c.key,
                name=c.name,
                order=c.order,
                score=str(category_scores[c.key]),
                maximum=str(iq_maximum(question_set)),
                dimension_keys=[d.key for d in question_set.dimensions_in_category(c.key)],
            )
            for c in question_set.categories
            if c.key in category_scores
        ],
        levels=[
            CompassLevelOut(
                key=level.key,
                name=level.name,
                order=place[level.key],
                min=level.min,
                max=level.max,
                text=level.text,
            )
            for level in levels
        ],
    )


def readiness_priorities(record: ReadinessRecord) -> list[PriorityItemOut]:
    question_set = record.question_set
    return [
        PriorityItemOut(
            rank=int(p["rank"]),
            key=str(p["key"]),
            name=question_set.dimension(str(p["key"])).name,
            score=int(p["score"]),
            maximum=question_set.dimension_max,
            level_name=None,
            next_steps=question_set.dimension(str(p["key"])).next_steps,
        )
        for p in record.result.priorities
    ]


def iq_priorities(record: IqRecord) -> list[PriorityItemOut]:
    question_set = record.question_set
    return [
        PriorityItemOut(
            rank=int(p["rank"]),
            key=str(p["key"]),
            name=question_set.dimension(str(p["key"])).name,
            score=int(p["score"]),
            maximum=question_set.iq_scale.max,
            level_name=stored_level(
                question_set, record.rows[str(p["key"])].level_key, int(p["score"])
            ).name,
            next_steps=question_set.dimension(str(p["key"])).next_steps,
        )
        for p in (record.assessment.priorities or [])
    ]
