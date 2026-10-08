"""Innovation Quotient, idea level (spec section 3).

``score_iq`` is the only public way to get an IQ. IQ never mixes with readiness (spec 4).
The IQ is always the book formula (spec 3.2). Client weights never change it (spec 3.4,
CONFIRMED, Amy, 2026-10-08); they only reorder priorities (``priorities.py``).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from app.scoring._rounding import IQ_DECIMAL_PLACES, rational_to_decimal
from app.scoring.errors import ScoringError, describe
from app.scoring.question_set import QUESTION_SET, IqLevel, QuestionSet


@dataclass(frozen=True, slots=True)
class DimensionIq:
    """One dimension's 1 to 10 score and its level (spec 3.1); None if not scored."""

    key: str
    name: str
    order: int
    category: str
    score: int | None
    level: IqLevel | None


@dataclass(frozen=True, slots=True)
class IqResult:
    """IQ of one idea (spec 3.2). ``iq`` is None unless all dimensions are scored."""

    question_set_version: int
    dimensions: tuple[DimensionIq, ...]
    iq: Decimal | None

    @property
    def complete(self) -> bool:
        """True when every dimension has a score."""
        return all(d.score is not None for d in self.dimensions)


def iq_level(score: int, question_set: QuestionSet = QUESTION_SET) -> IqLevel:
    """The level of one 1 to 10 dimension score, inclusive ranges (spec 3.1)."""
    _validate_score("score", score, question_set)
    for level in question_set.iq_levels:
        if level.min <= score <= level.max:
            return level
    raise ScoringError(f"No IQ level covers {describe(score)}")  # unreachable after validation


def iq_minimum(question_set: QuestionSet = QUESTION_SET) -> Decimal:
    """The lowest possible IQ: every dimension at the bottom of the scale (spec 3.2: 10)."""
    bottom = len(question_set.dimensions) * question_set.iq_scale.min
    return _book_iq(bottom, question_set)


def iq_maximum(question_set: QuestionSet = QUESTION_SET) -> Decimal:
    """The highest possible IQ: every dimension at the top of the scale (spec 3.2: 100)."""
    top = len(question_set.dimensions) * question_set.iq_scale.max
    return _book_iq(top, question_set)


def _validate_score(key: str, value: object, question_set: QuestionSet) -> int:
    scale = question_set.iq_scale
    if not isinstance(value, int) or isinstance(value, bool):
        raise ScoringError(
            f"IQ score for {key} must be a whole number {scale.min} to {scale.max}, "
            f"got {describe(value)}"
        )
    if not scale.min <= value <= scale.max:
        raise ScoringError(
            f"IQ score for {key} must be {scale.min} to {scale.max}, got {describe(value)}"
        )
    return value


def _validated_scores(scores: Mapping[str, object], question_set: QuestionSet) -> dict[str, int]:
    if not isinstance(scores, Mapping):
        raise ScoringError(
            f"Scores must be a mapping of dimension key to score, got {describe(scores)}"
        )
    valid: dict[str, int] = {}
    for key, value in scores.items():
        if not isinstance(key, str):
            raise ScoringError(f"Dimension key must be text, got {describe(key)}")
        question_set.dimension(key)
        if value is None:
            continue
        valid[key] = _validate_score(key, value, question_set)
    return valid


def _book_iq(total: int, question_set: QuestionSet) -> Decimal:
    """Spec 3.2: iq = sum / (12 x 10) x 100, rounded once to 1 decimal."""
    maximum = len(question_set.dimensions) * question_set.iq_scale.max
    return rational_to_decimal(Fraction(total * 100, maximum), IQ_DECIMAL_PLACES)


def score_iq(
    scores: Mapping[str, object],
    *,
    question_set: QuestionSet = QUESTION_SET,
) -> IqResult:
    """Score one idea (spec 3.1 levels, 3.2 IQ formula).

    ``scores`` maps dimension keys to integers 1 to 10; a missing key or None means not
    scored, which makes the result incomplete with ``iq`` None (never counted as 0).
    The IQ is sum / 120 x 100, rounded once to 1 decimal. There is no weights argument:
    weights never change the IQ (spec 3.4).
    """
    valid = _validated_scores(scores, question_set)
    dimensions = tuple(
        DimensionIq(
            key=d.key,
            name=d.name,
            order=d.order,
            category=d.category,
            score=valid.get(d.key),
            level=iq_level(valid[d.key], question_set) if d.key in valid else None,
        )
        for d in question_set.dimensions
    )
    iq: Decimal | None = None
    if len(valid) == len(question_set.dimensions):
        iq = _book_iq(sum(valid.values()), question_set)
    return IqResult(question_set_version=question_set.version, dimensions=dimensions, iq=iq)
