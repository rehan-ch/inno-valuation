"""Targets and gaps per dimension (spec section 6, granularity pending Q8).

Readiness and IQ targets are computed separately; no function takes both.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.scoring._guards import require_same_version
from app.scoring.errors import ScoringError, describe
from app.scoring.iq import IqResult
from app.scoring.question_set import QUESTION_SET, QuestionSet
from app.scoring.readiness import ReadinessResult


@dataclass(frozen=True, slots=True)
class TargetGap:
    """One dimension's target and gap. ``gap`` = target - current, None if unscored."""

    key: str
    name: str
    order: int
    current: int | None
    target: int
    gap: int | None


@dataclass(frozen=True, slots=True)
class TargetsResult:
    """Gaps for the dimensions that have a target, in book order (spec 6)."""

    question_set_version: int
    items: tuple[TargetGap, ...]


def _validated_targets(
    targets: Mapping[str, object], low: int, high: int, question_set: QuestionSet
) -> dict[str, int]:
    if not isinstance(targets, Mapping):
        raise ScoringError(
            f"Targets must be a mapping of dimension key to target, got {describe(targets)}"
        )
    valid: dict[str, int] = {}
    for key, value in targets.items():
        if not isinstance(key, str):
            raise ScoringError(f"Dimension key must be text, got {describe(key)}")
        question_set.dimension(key)
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ScoringError(
                f"Target for {key} must be a whole number {low} to {high}, got {describe(value)}"
            )
        valid[key] = value
    return valid


def _gaps(
    current: Mapping[str, int | None], targets: Mapping[str, int], question_set: QuestionSet
) -> tuple[TargetGap, ...]:
    items = []
    for dimension in question_set.dimensions:
        if dimension.key not in targets:
            continue
        now = current[dimension.key]
        target = targets[dimension.key]
        items.append(
            TargetGap(
                key=dimension.key,
                name=dimension.name,
                order=dimension.order,
                current=now,
                target=target,
                gap=None if now is None else target - now,
            )
        )
    return tuple(items)


# PROVISIONAL: see open-questions Q8
def readiness_targets(
    result: ReadinessResult,
    targets: Mapping[str, object],
    question_set: QuestionSet = QUESTION_SET,
) -> TargetsResult:
    """Readiness gap per dimension: target (5 to 25, derived) minus current score (spec 6)."""
    require_same_version(
        result.question_set_version, [d.key for d in result.dimensions], question_set
    )
    valid = _validated_targets(
        targets, question_set.dimension_min, question_set.dimension_max, question_set
    )
    current = {d.key: d.score for d in result.dimensions}
    return TargetsResult(
        question_set_version=result.question_set_version,
        items=_gaps(current, valid, question_set),
    )


# PROVISIONAL: see open-questions Q8
def iq_targets(
    result: IqResult,
    targets: Mapping[str, object],
    question_set: QuestionSet = QUESTION_SET,
) -> TargetsResult:
    """IQ gap per dimension: target (1 to 10) minus current score (spec 6)."""
    require_same_version(
        result.question_set_version, [d.key for d in result.dimensions], question_set
    )
    valid = _validated_targets(
        targets, question_set.iq_scale.min, question_set.iq_scale.max, question_set
    )
    current = {d.key: d.score for d in result.dimensions}
    return TargetsResult(
        question_set_version=result.question_set_version,
        items=_gaps(current, valid, question_set),
    )
