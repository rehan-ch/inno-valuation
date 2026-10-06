"""Priorities: the lowest-scoring dimensions (spec section 7).

Readiness and IQ priorities are computed separately; no function takes both.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.scoring._guards import require_complete, require_same_version
from app.scoring.iq import IqResult
from app.scoring.question_set import QUESTION_SET, QuestionSet
from app.scoring.readiness import ReadinessResult

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


def _lowest_dimensions(
    scored: Sequence[tuple[str, str, int, int]], count: int
) -> tuple[PriorityItem, ...]:
    """Rank (key, name, book order, score) rows: lower score first, then book order."""
    ranked = sorted(
        scored,
        key=lambda row: (row[3], row[2]),  # PROVISIONAL: see open-questions Q19
    )
    return tuple(
        PriorityItem(rank=i, key=key, name=name, score=score)
        for i, (key, name, _order, score) in enumerate(ranked[:count], start=1)
    )


def readiness_priorities(
    result: ReadinessResult, question_set: QuestionSet = QUESTION_SET
) -> PriorityResult:
    """The 5 lowest readiness dimension scores (spec 7). Needs a complete result."""
    require_same_version(
        result.question_set_version, [d.key for d in result.dimensions], question_set
    )
    require_complete(result.complete, "Readiness priorities")
    rows = [(d.key, d.name, d.order, d.score) for d in result.dimensions if d.score is not None]
    return PriorityResult(
        question_set_version=result.question_set_version,
        items=_lowest_dimensions(rows, PRIORITY_COUNT),
    )


def iq_priorities(result: IqResult, question_set: QuestionSet = QUESTION_SET) -> PriorityResult:
    """The 5 lowest IQ dimension scores of one idea (spec 7). Needs a complete result."""
    require_same_version(
        result.question_set_version, [d.key for d in result.dimensions], question_set
    )
    require_complete(result.complete, "IQ priorities")
    rows = [(d.key, d.name, d.order, d.score) for d in result.dimensions if d.score is not None]
    return PriorityResult(
        question_set_version=result.question_set_version,
        items=_lowest_dimensions(rows, PRIORITY_COUNT),
    )
