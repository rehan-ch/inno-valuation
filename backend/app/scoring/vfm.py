"""Value for Money (spec section 5): cost per innovation point. Lower is better."""

from decimal import Decimal

from app.scoring._rounding import VFM_DECIMAL_PLACES, engine_math, quantize
from app.scoring.errors import ScoringError, describe
from app.scoring.iq import iq_maximum, iq_minimum
from app.scoring.question_set import QUESTION_SET, QuestionSet

# ISO 4217: the largest minor-unit exponent of any currency is 4 (CLF, UYW).
MAX_MINOR_UNIT_EXPONENT = 4


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# PROVISIONAL: see open-questions Q18 (VfM divides by the rounded IQ)
def vfm(
    cost_minor: int | None,
    minor_unit_exponent: int,
    iq: Decimal | int | None,
    question_set: QuestionSet = QUESTION_SET,
) -> Decimal | None:
    """Value for Money = investment cost / IQ, rounded to 2 decimals (spec 5.1, 5.2).

    For an idea, the cost is the total planned or known investment in the idea. The same
    calculation serves a procurement opportunity: total purchase value / IQ (spec 5.2).
    VfM for a whole dimension is not defined and is out of Version 1 (spec 5.2).

    ``cost_minor`` is the cost in minor units (for example cents) and
    ``minor_unit_exponent`` the currency's number of minor-unit digits (2 for EUR, 0 for
    JPY). The cost is converted to major units once, here. ``iq`` is the IQ shown to the
    user (``IqResult.iq``). Returns None when the cost is missing, or the IQ is missing or
    0. Raises ScoringError for negative values, an IQ outside 10 to 100 other than 0
    (spec 3.2), a float IQ, a non-integer cost, or an exponent outside 0 to 4.
    """
    if not _is_int(minor_unit_exponent) or not (
        0 <= minor_unit_exponent <= MAX_MINOR_UNIT_EXPONENT
    ):
        raise ScoringError(
            f"Minor unit exponent must be a whole number 0 to {MAX_MINOR_UNIT_EXPONENT} "
            f"(ISO 4217), got {describe(minor_unit_exponent)}"
        )
    if cost_minor is not None:
        if not _is_int(cost_minor):
            raise ScoringError(
                f"Cost must be an integer in minor units, got {describe(cost_minor)}"
            )
        if cost_minor < 0:
            raise ScoringError(f"Cost must not be negative, got {describe(cost_minor)}")
    if iq is not None:
        if isinstance(iq, bool) or not isinstance(iq, int | Decimal):
            raise ScoringError(f"IQ must be a Decimal or an integer, got {describe(iq)}")
        if isinstance(iq, Decimal) and not iq.is_finite():
            raise ScoringError(f"IQ must be finite, got {describe(iq)}")
        if iq < 0:
            raise ScoringError(f"IQ must not be negative, got {describe(iq)}")
        minimum, maximum = iq_minimum(question_set), iq_maximum(question_set)
        if iq > maximum:
            raise ScoringError(f"IQ must not be above {maximum}, got {describe(iq)}")
        if 0 < iq < minimum:
            raise ScoringError(f"IQ must be 0 or {minimum} to {maximum}, got {describe(iq)}")
    if cost_minor is None or iq is None or iq == 0:
        return None
    with engine_math():
        cost_major = Decimal(cost_minor).scaleb(-minor_unit_exponent)
        return quantize(cost_major / Decimal(iq), VFM_DECIMAL_PLACES)
