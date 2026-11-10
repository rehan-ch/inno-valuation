"""Change between two results of the same kind over time (spec section 9).

A new assessment never overwrites an old one; the app compares results per dimension and
shows improvement or decline. Comparisons use the same ``question_set_version`` only.
Readiness and IQ are compared separately; no function takes both (spec 4).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.scoring._rounding import engine_math
from app.scoring.errors import ScoringError, describe
from app.scoring.question_set import QUESTION_SET, QuestionSet


class Direction(StrEnum):
    """Which way a number moved. It says nothing about better or worse."""

    UP = "up"
    DOWN = "down"
    SAME = "same"


@dataclass(frozen=True, slots=True)
class Change[N: (int, Decimal)]:
    """``change`` = current - previous, exactly; never rounded again."""

    previous: N
    current: N
    change: N
    direction: Direction


@dataclass(frozen=True, slots=True)
class DimensionChange:
    """One dimension's score in two results, in book order."""

    key: str
    name: str
    order: int
    change: Change[int]


def _direction(change: int | Decimal) -> Direction:
    if change > 0:
        return Direction.UP
    if change < 0:
        return Direction.DOWN
    return Direction.SAME


def _whole(what: str, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ScoringError(f"{what} must be a whole number, got {describe(value)}")
    return value


def whole_change(previous: object, current: object) -> Change[int]:
    """Change between two whole-number scores or totals (spec 9)."""
    before = _whole("Previous value", previous)
    now = _whole("Current value", current)
    change = now - before
    return Change(previous=before, current=now, change=change, direction=_direction(change))


def decimal_change(previous: object, current: object) -> Change[Decimal]:
    """Change between two decimal figures as shown (an IQ, a Value for Money), exact: the
    difference of two rounded figures needs no rounding of its own (spec 9)."""
    if not isinstance(previous, Decimal) or not previous.is_finite():
        raise ScoringError(f"Previous value must be a finite Decimal, got {describe(previous)}")
    if not isinstance(current, Decimal) or not current.is_finite():
        raise ScoringError(f"Current value must be a finite Decimal, got {describe(current)}")
    with engine_math():
        change = current - previous
    return Change(previous=previous, current=current, change=change, direction=_direction(change))


def require_comparable(previous_version: object, current_version: object) -> None:
    """Spec 9: two results are compared only on the same ``question_set_version``."""
    if previous_version != current_version:
        raise ScoringError(
            f"Results on question set versions {describe(previous_version)} and "
            f"{describe(current_version)} cannot be compared"
        )


def dimension_changes(
    previous: Mapping[str, object],
    current: Mapping[str, object],
    *,
    previous_version: int,
    current_version: int,
    question_set: QuestionSet = QUESTION_SET,
) -> tuple[DimensionChange, ...]:
    """Per-dimension change between two complete results, in book order (spec 9).

    Both results must be on ``question_set``'s version and hold every dimension; anything
    else raises ScoringError, so a comparison across versions can never be shown.
    """
    require_comparable(previous_version, current_version)
    require_comparable(current_version, question_set.version)
    for name, scores in (("Previous", previous), ("Current", current)):
        if not isinstance(scores, Mapping):
            raise ScoringError(f"{name} scores must be a mapping, got {describe(scores)}")
        if set(scores) != set(question_set.dimension_keys):
            raise ScoringError(f"{name} scores must hold every dimension exactly once")
    return tuple(
        DimensionChange(
            key=d.key,
            name=d.name,
            order=d.order,
            change=whole_change(previous[d.key], current[d.key]),
        )
        for d in question_set.dimensions
    )
