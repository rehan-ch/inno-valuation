"""ISO 4217 minor units: how many decimal places a currency has.

Money is stored in whole minor units (cents, pence, fils) so no float ever touches it. The
conversion to and from major units happens here and nowhere else. Most currencies have 2
decimals; the exceptions below are the ISO 4217 list.
"""

from decimal import Decimal
from typing import Final

_ZERO_DECIMALS: Final = frozenset(
    {
        "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "UYI",
        "VND", "VUV", "XAF", "XOF", "XPF",
    }
)  # fmt: skip
_THREE_DECIMALS: Final = frozenset({"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"})
_FOUR_DECIMALS: Final = frozenset({"CLF", "UYW"})
_DEFAULT_DECIMALS: Final = 2


def minor_unit_exponent(currency: str) -> int:
    """The currency's number of minor-unit digits: 2 for USD and EUR, 0 for JPY, 3 for KWD."""
    if currency in _ZERO_DECIMALS:
        return 0
    if currency in _THREE_DECIMALS:
        return 3
    if currency in _FOUR_DECIMALS:
        return 4
    return _DEFAULT_DECIMALS


def to_minor_units(amount: Decimal, currency: str) -> int:
    """``Decimal("50000.00")`` in USD is 5,000,000 cents. ValueError when the amount has more
    decimals than the currency, so nothing is silently rounded."""
    exponent = minor_unit_exponent(currency)
    scaled = amount.scaleb(exponent)
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{currency} amounts have at most {exponent} decimal places")
    return int(scaled)


def to_major_units(minor: int, currency: str) -> Decimal:
    """5,000,000 cents in USD is ``Decimal("50000.00")``, with the currency's decimals."""
    exponent = minor_unit_exponent(currency)
    return Decimal(minor).scaleb(-exponent).quantize(Decimal(1).scaleb(-exponent))
