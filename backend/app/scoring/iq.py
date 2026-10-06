"""Innovation Quotient, idea level (spec section 3).

``score_iq`` is the only public way to get an IQ. IQ never mixes with readiness (spec 4).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from app.scoring._rounding import IQ_DECIMAL_PLACES, engine_math, rational_to_decimal
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
    """IQ of one idea (spec 3.2, 3.4).

    ``iq`` is None unless all dimensions are scored. ``weights`` holds the custom weights
    used, as Decimals in book order, or None for the book formula.
    """

    question_set_version: int
    dimensions: tuple[DimensionIq, ...]
    iq: Decimal | None
    weights: tuple[tuple[str, Decimal], ...] | None

    @property
    def complete(self) -> bool:
        """True when every dimension has a score."""
        return all(d.score is not None for d in self.dimensions)

    @property
    def weighted(self) -> bool:
        """True when custom weights were applied."""
        return self.weights is not None


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


@dataclass(frozen=True, slots=True)
class WeightLimits:
    """Allowed range and precision of one custom weight."""

    minimum: int
    maximum: int
    max_decimal_places: int


# PROVISIONAL: see open-questions Q22
WEIGHT_LIMITS = WeightLimits(minimum=0, maximum=1000, max_decimal_places=6)


def _validated_weight(key: str, value: object) -> Decimal:
    """One weight as a plain, normalised Decimal (no -0, no exponent form)."""
    limits = WEIGHT_LIMITS
    if isinstance(value, float):
        raise ScoringError(
            f"Weight for {key} must be an integer or a Decimal, not a float, got {describe(value)}"
        )
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        raise ScoringError(f"Weight for {key} must be a number, got {describe(value)}")
    if isinstance(value, Decimal) and not value.is_finite():
        raise ScoringError(f"Weight for {key} must be finite, got {describe(value)}")
    if not limits.minimum <= value <= limits.maximum:
        raise ScoringError(
            f"Weight for {key} must be {limits.minimum} to {limits.maximum}, got {describe(value)}"
        )
    if value == 0:
        return Decimal(0)
    with engine_math():
        normalised = Decimal(value).normalize()
    exponent = normalised.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -limits.max_decimal_places:
        raise ScoringError(
            f"Weight for {key} may have at most {limits.max_decimal_places} decimal places, "
            f"got {describe(value)}"
        )
    return Decimal(f"{normalised:f}")


# PROVISIONAL: see open-questions Q2
def _validated_weights(
    weights: Mapping[str, object], question_set: QuestionSet
) -> dict[str, Decimal]:
    """Weights per dimension: exactly the 12 keys, within WEIGHT_LIMITS, not all zero."""
    if not isinstance(weights, Mapping):
        raise ScoringError(
            f"Weights must be a mapping of dimension key to weight, got {describe(weights)}"
        )
    keys = set(question_set.dimension_keys)
    unknown = sorted(str(k) for k in weights if k not in keys)
    if unknown:
        raise ScoringError(f"Unknown dimension keys in weights: {unknown}")
    missing = [k for k in question_set.dimension_keys if k not in weights]
    if missing:
        raise ScoringError(f"Weights missing for dimensions: {missing}")
    valid = {k: _validated_weight(k, weights[k]) for k in question_set.dimension_keys}
    if not any(valid.values()):
        raise ScoringError("At least one weight must be above zero")
    return valid


# PROVISIONAL: see open-questions Q2
def _weighted_iq(
    scores: Mapping[str, int], weights: Mapping[str, Decimal], question_set: QuestionSet
) -> Decimal:
    """Weighted mean of the scores, normalised to the 0 to 100 IQ scale, 1 decimal.

    iq = sum(w x s) x 100 / (sum(w) x 10). Weights are normalised by their sum, so they do
    not need to add up to 1. The maths is exact (Fraction) and rounded once, so equal
    weights give exactly the book IQ.
    """
    exact = {k: Fraction(w) for k, w in weights.items()}
    weighted_sum = sum((exact[k] * scores[k] for k in question_set.dimension_keys), Fraction(0))
    weight_total = sum(exact.values(), Fraction(0))
    value = weighted_sum * 100 / (weight_total * question_set.iq_scale.max)
    return rational_to_decimal(value, IQ_DECIMAL_PLACES)


def score_iq(
    scores: Mapping[str, object],
    weights: Mapping[str, object] | None = None,
    question_set: QuestionSet = QUESTION_SET,
) -> IqResult:
    """Score one idea (spec 3.1 levels, 3.2 book IQ, 3.4 weights).

    ``scores`` maps dimension keys to integers 1 to 10; a missing key or None means not
    scored, which makes the result incomplete with ``iq`` None (never counted as 0).
    Without ``weights`` the book formula is used. With weights, the PROVISIONAL weighted
    formula (open-questions Q2) is used.
    """
    valid = _validated_scores(scores, question_set)
    valid_weights = _validated_weights(weights, question_set) if weights is not None else None
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
        if valid_weights is None:
            iq = _book_iq(sum(valid.values()), question_set)
        else:
            iq = _weighted_iq(valid, valid_weights, question_set)
    stored_weights: tuple[tuple[str, Decimal], ...] | None = None
    if valid_weights is not None:
        stored_weights = tuple((k, valid_weights[k]) for k in question_set.dimension_keys)
    return IqResult(
        question_set_version=question_set.version,
        dimensions=dimensions,
        iq=iq,
        weights=stored_weights,
    )
