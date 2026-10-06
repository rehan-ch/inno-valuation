"""Fixed Decimal arithmetic for the engine (spec sections 3.2 and 5.1).

Every division, multiplication and quantize in the engine runs inside ``engine_math()``,
so results never depend on the caller's Decimal context.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import (
    ROUND_HALF_UP,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    Underflow,
    localcontext,
)
from fractions import Fraction

from app.scoring.errors import ScoringError

ROUNDING = ROUND_HALF_UP  # PROVISIONAL: see open-questions Q18

# Spec 3.2: IQ is rounded to 1 decimal. Spec 5.1: VfM is rounded to 2 decimals.
IQ_DECIMAL_PLACES = 1
VFM_DECIMAL_PLACES = 2

_ENGINE_CONTEXT = Context(
    prec=50,
    rounding=ROUNDING,
    Emin=-999_999,
    Emax=999_999,
    capitals=1,
    clamp=0,
    flags=[],
    traps=[InvalidOperation, DivisionByZero, Overflow, Underflow],
)


@contextmanager
def engine_math() -> Iterator[Context]:
    """Run Decimal arithmetic in _ENGINE_CONTEXT; any Decimal error becomes ScoringError."""
    try:
        with localcontext(_ENGINE_CONTEXT) as ctx:
            yield ctx
    except DecimalException as exc:
        raise ScoringError(f"Arithmetic error in the scoring engine: {exc!r}") from exc


def quantize(value: Decimal, places: int) -> Decimal:
    """Round ``value`` to ``places`` decimals with ROUNDING, inside the engine context."""
    with engine_math():
        return value.quantize(Decimal(1).scaleb(-places), rounding=ROUNDING)


def rational_to_decimal(value: Fraction, places: int) -> Decimal:
    """Turn an exact rational into a Decimal rounded once to ``places`` decimals."""
    with engine_math():
        exact = Decimal(value.numerator) / Decimal(value.denominator)
        return quantize(exact, places)
