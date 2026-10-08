"""Priorities: the lowest-scoring dimensions (spec section 7).

Readiness and IQ priorities are computed separately; no function takes both. Client
weights may reorder the list (spec 7, CONFIRMED, Amy, 2026-10-08, open-questions Q2) but
never change a score: every item shows the dimension score exactly as in the result.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from app.scoring._guards import require_complete, require_same_version
from app.scoring.iq import IqResult
from app.scoring.question_set import QUESTION_SET, QuestionSet
from app.scoring.readiness import ReadinessResult
from app.scoring.weights import validate_weights

# Spec 7: "Normally the lowest 5."
PRIORITY_COUNT = 5  # PROVISIONAL: see open-questions Q21


@dataclass(frozen=True, slots=True)
class PriorityItem:
    """One prioritised dimension. Rank 1 is the most urgent."""

    rank: int
    key: str
    name: str
    score: int


@dataclass(frozen=True, slots=True)
class PriorityResult:
    """The ranked lowest dimensions of one readiness or IQ result (spec 7)."""

    question_set_version: int
    items: tuple[PriorityItem, ...]


@dataclass(frozen=True, slots=True)
class _Row:
    key: str
    name: str
    order: int
    score: int
    weight: Fraction


def _rank_key(row: _Row) -> tuple[int, Fraction, int]:
    """Sort key: lower score first, then higher weight, then book order (spec 7)."""
    return (
        row.score,
        -row.weight,  # PROVISIONAL: see open-questions Q23
        row.order,  # PROVISIONAL: see open-questions Q19
    )


def _lowest_dimensions(rows: Sequence[_Row], count: int) -> tuple[PriorityItem, ...]:
    """The ``count`` most urgent rows, ranked by ``_rank_key``."""
    ranked = sorted(rows, key=_rank_key)
    return tuple(
        PriorityItem(rank=i, key=row.key, name=row.name, score=row.score)
        for i, row in enumerate(ranked[:count], start=1)
    )


def _weights_or_equal(
    weights: Mapping[str, object] | None, question_set: QuestionSet
) -> dict[str, Fraction]:
    """Validated weights as exact Fractions, or one equal weight each when none are given.

    Converted once here, so ranking never depends on the caller's Decimal context.
    """
    if weights is None:
        return dict.fromkeys(question_set.dimension_keys, Fraction(1))
    valid = validate_weights(weights, question_set=question_set)
    return {key: Fraction(weight) for key, weight in valid.items()}


def readiness_priorities(
    result: ReadinessResult,
    weights: Mapping[str, object] | None = None,
    *,
    question_set: QuestionSet = QUESTION_SET,
) -> PriorityResult:
    """The 5 lowest readiness dimension scores (spec 7). Needs a complete result.

    Optional client ``weights`` (validated as in ``weights.validate_weights``) only break
    ties between equal scores, higher weight first (PROVISIONAL, open-questions Q23).
    Without weights, or with equal weights, ties go by book order.
    """
    require_same_version(
        result.question_set_version, [d.key for d in result.dimensions], question_set
    )
    valid_weights = _weights_or_equal(weights, question_set)
    require_complete(result.complete, "Readiness priorities")
    rows = [
        _Row(d.key, d.name, d.order, d.score, valid_weights[d.key])
        for d in result.dimensions
        if d.score is not None
    ]
    return PriorityResult(
        question_set_version=result.question_set_version,
        items=_lowest_dimensions(rows, PRIORITY_COUNT),
    )


def iq_priorities(
    result: IqResult,
    weights: Mapping[str, object] | None = None,
    *,
    question_set: QuestionSet = QUESTION_SET,
) -> PriorityResult:
    """The 5 lowest IQ dimension scores of one idea (spec 7). Needs a complete result.

    Optional client ``weights`` (validated as in ``weights.validate_weights``) only break
    ties between equal scores, higher weight first (PROVISIONAL, open-questions Q23).
    Without weights, or with equal weights, ties go by book order.
    """
    require_same_version(
        result.question_set_version, [d.key for d in result.dimensions], question_set
    )
    valid_weights = _weights_or_equal(weights, question_set)
    require_complete(result.complete, "IQ priorities")
    rows = [
        _Row(d.key, d.name, d.order, d.score, valid_weights[d.key])
        for d in result.dimensions
        if d.score is not None
    ]
    return PriorityResult(
        question_set_version=result.question_set_version,
        items=_lowest_dimensions(rows, PRIORITY_COUNT),
    )
