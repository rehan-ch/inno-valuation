"""Client dimension weights (spec 3.4 and 7).

Spec 3.4 (CONFIRMED, Amy, 2026-10-08, open-questions Q2): weights never change any score.
They only change the order of the priorities list (spec 7, see ``priorities.py``). This
module only validates them; it does no arithmetic with scores.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from app.scoring._rounding import engine_math
from app.scoring.errors import ScoringError, describe
from app.scoring.question_set import QUESTION_SET, QuestionSet


@dataclass(frozen=True, slots=True)
class WeightLimits:
    """Allowed range and precision of one client weight."""

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


def validate_weights(
    weights: Mapping[str, object], *, question_set: QuestionSet = QUESTION_SET
) -> Mapping[str, Decimal]:
    """Validate client weights (spec 3.4; limits PROVISIONAL, open-questions Q22).

    Weights must cover exactly the dimension keys of ``question_set``, each an int or a
    Decimal (never a float) within ``WEIGHT_LIMITS``, and not all zero. They need not add
    up to anything. Returns a read-only mapping of normalised Decimals in book order.
    Raises ScoringError otherwise. Validating the output again returns equal values.

    Store this output as the assessment's weights snapshot and pass the snapshot back to
    ``readiness_priorities`` or ``iq_priorities``.
    """
    if not isinstance(weights, Mapping):
        raise ScoringError(
            f"Weights must be a mapping of dimension key to weight, got {describe(weights)}"
        )
    keys = set(question_set.dimension_keys)
    unknown = sorted(describe(k) for k in weights if k not in keys)
    if unknown:
        raise ScoringError(f"Unknown dimension keys in weights: {', '.join(unknown)}")
    missing = [k for k in question_set.dimension_keys if k not in weights]
    if missing:
        raise ScoringError(f"Weights missing for dimensions: {missing}")
    valid = {k: _validated_weight(k, weights[k]) for k in question_set.dimension_keys}
    # Part of the provisional Q22 limits above: all zeros is treated as a mistake.
    if not any(valid.values()):
        raise ScoringError("At least one weight must be above zero")
    return MappingProxyType(valid)
