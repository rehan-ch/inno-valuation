"""Value for Money (spec section 5 and the VfM golden examples in section 11)."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import app.scoring.vfm as vfm_module
from app.scoring.errors import ScoringError
from app.scoring.iq import score_iq
from app.scoring.vfm import vfm
from tests.scoring.support import iq_scores_for_sum

# --- golden examples (spec 11) -----------------------------------------------------------


@pytest.mark.parametrize(
    ("cost_minor", "exponent", "iq", "expected"),
    [
        pytest.param(5_000_000, 2, 70, "714.29", id="50,000 and IQ 70"),
        pytest.param(5_000_000, 2, Decimal("70.0"), "714.29", id="50,000 and IQ 70.0"),
        pytest.param(30_000_000, 2, 84, "3571.43", id="300,000 and IQ 84"),
        pytest.param(50_000, 0, 70, "714.29", id="exponent 0"),
        pytest.param(50_000_000, 3, 70, "714.29", id="exponent 3"),
    ],
)
def test_golden_examples(cost_minor: int, exponent: int, iq: Any, expected: str) -> None:
    result = vfm(cost_minor, exponent, iq)
    assert result == Decimal(expected)
    assert str(result) == expected


def test_vfm_from_a_scored_idea_uses_the_rounded_iq() -> None:
    """Q18 example: sum 83 gives IQ 69.2 and VfM 722.54 (not 722.89 from 69.1666...)."""
    iq = score_iq(iq_scores_for_sum(83)).iq
    assert iq == Decimal("69.2")
    assert vfm(5_000_000, 2, iq) == Decimal("722.54")


def test_vfm_rounds_half_up() -> None:
    """0.05 / 10 = 0.005 exactly, shown as 0.01 (PROVISIONAL Q18)."""
    assert vfm(5, 2, 10) == Decimal("0.01")


def test_zero_cost_gives_zero() -> None:
    assert str(vfm(0, 2, 70)) == "0.00"


@pytest.mark.parametrize(
    ("cost_minor", "iq"),
    [
        pytest.param(5_000_000, 0, id="IQ 0"),
        pytest.param(5_000_000, Decimal("0.0"), id="IQ 0.0"),
        pytest.param(5_000_000, None, id="IQ missing"),
        pytest.param(None, 70, id="cost missing"),
        pytest.param(None, None, id="both missing"),
    ],
)
def test_nil_cases(cost_minor: int | None, iq: Any) -> None:
    assert vfm(cost_minor, 2, iq) is None


def test_incomplete_idea_gives_nil() -> None:
    assert vfm(5_000_000, 2, score_iq({}).iq) is None


@pytest.mark.parametrize(
    ("cost_minor", "exponent", "iq", "message"),
    [
        pytest.param(-1, 2, 70, "Cost must not be negative", id="negative cost"),
        pytest.param(5.0, 2, 70, "Cost must be an integer", id="float cost"),
        pytest.param(True, 2, 70, "Cost must be an integer", id="bool cost"),
        pytest.param("500", 2, 70, "Cost must be an integer", id="text cost"),
        pytest.param(Decimal(500), 2, 70, "Cost must be an integer", id="Decimal cost"),
        pytest.param(500, -1, 70, "0 to 4", id="negative exponent"),
        pytest.param(500, 5, 70, "0 to 4", id="exponent 5"),
        pytest.param(500, 10**7, 70, "0 to 4", id="huge exponent"),
        pytest.param(500, 2, 1, "0 or 10.0 to 100.0", id="IQ 1"),
        pytest.param(500, 2, 9, "0 or 10.0 to 100.0", id="IQ 9"),
        pytest.param(500, 2, Decimal("9.9"), "0 or 10.0 to 100.0", id="IQ 9.9"),
        pytest.param(500, 2, Decimal("0.1"), "0 or 10.0 to 100.0", id="IQ 0.1"),
        pytest.param(None, 2, 5, "0 or 10.0 to 100.0", id="IQ 5, cost missing"),
        pytest.param(-(10**10_000), 2, 70, "too large to show", id="huge negative cost"),
        pytest.param(500, 2.0, 70, "exponent", id="float exponent"),
        pytest.param(500, True, 70, "exponent", id="bool exponent"),
        pytest.param(500, None, 70, "exponent", id="missing exponent"),
        pytest.param(500, 2, -1, "IQ must not be negative", id="negative IQ"),
        pytest.param(500, 2, Decimal("-0.1"), "IQ must not be negative", id="negative IQ Decimal"),
        pytest.param(500, 2, Decimal("100.1"), "above 100", id="IQ above max"),
        pytest.param(500, 2, 101, "above 100", id="int IQ above max"),
        pytest.param(500, 2, 70.0, "Decimal or an integer", id="float IQ"),
        pytest.param(500, 2, True, "Decimal or an integer", id="bool IQ"),
        pytest.param(500, 2, "70", "Decimal or an integer", id="text IQ"),
        pytest.param(500, 2, Decimal("NaN"), "finite", id="NaN IQ"),
        pytest.param(500, 2, Decimal("sNaN"), "finite", id="sNaN IQ"),
        pytest.param(500, 2, Decimal("Infinity"), "finite", id="infinite IQ"),
        pytest.param(None, 2, 70.0, "Decimal or an integer", id="float IQ, cost missing"),
        pytest.param(None, 2, -5, "IQ must not be negative", id="negative IQ, cost missing"),
        pytest.param(-1, 2, None, "Cost must not be negative", id="negative cost, IQ missing"),
    ],
)
def test_invalid_input_is_rejected(cost_minor: Any, exponent: Any, iq: Any, message: str) -> None:
    with pytest.raises(ScoringError, match=message):
        vfm(cost_minor, exponent, iq)


def test_iq_of_exactly_100_is_allowed() -> None:
    assert vfm(10_000, 2, Decimal("100.0")) == Decimal("1.00")


@pytest.mark.parametrize("iq", [10, Decimal("10.0"), Decimal("10.1")])
def test_iq_at_the_scale_minimum_is_allowed(iq: Any) -> None:
    assert vfm(10_000, 2, iq) is not None


@pytest.mark.parametrize(("exponent", "expected"), [(0, "100000.00"), (4, "10.00")])
def test_exponent_bounds_are_accepted(exponent: int, expected: str) -> None:
    assert str(vfm(1_000_000, exponent, 10)) == expected


@pytest.mark.parametrize(
    ("cost_minor", "exponent"),
    [
        (10**40, 2),
        (10**47, 2),
        (10**60, 2),
        (10**200, 2),
        (2**4000, 0),
        (5, 4),
        (10**49, 4),
    ],
)
def test_huge_values_give_a_value_or_scoring_error(cost_minor: int, exponent: int) -> None:
    try:
        result = vfm(cost_minor, exponent, 70)
    except ScoringError:
        return
    assert isinstance(result, Decimal)
    assert result.as_tuple().exponent == -2


def test_large_but_representable_cost() -> None:
    assert str(vfm(10**40, 2, 10)) == f"{10**37}.00"


def test_cost_too_large_for_the_engine_raises_scoring_error() -> None:
    with pytest.raises(ScoringError, match="Arithmetic error"):
        vfm(10**60, 2, 70)


def test_only_the_q18_marker_sits_directly_above_def_vfm() -> None:
    """Q7 is decided (spec 5.2), so only the Q18 rounding marker remains."""
    lines = Path(vfm_module.__file__).read_text(encoding="utf-8").splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("def vfm("))
    assert lines[index - 2 : index] == [
        "",
        "# PROVISIONAL: see open-questions Q18 (VfM divides by the rounded IQ)",
    ]
    assert not any("open-questions Q7" in line for line in lines)


def test_procurement_opportunity_uses_the_same_calculation() -> None:
    """Spec 5.2: total purchase value / IQ, currency per innovation point."""
    total_purchase_value_minor = 30_000_000
    assert vfm(total_purchase_value_minor, 2, 84) == Decimal("3571.43")
