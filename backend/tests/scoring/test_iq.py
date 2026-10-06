"""Innovation Quotient (spec section 3 and the IQ golden examples in section 11)."""

import dataclasses
import math
import time
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

import app.scoring.iq as iq_module
from app.scoring.errors import ScoringError
from app.scoring.iq import WEIGHT_LIMITS, iq_level, iq_maximum, iq_minimum, score_iq
from tests.scoring.support import KEYS, QS, iq_scores, iq_scores_for_sum

# (score, level name) per spec 3.1, every value on the scale.
LEVEL_TABLE = [
    (1, "Continuous Improvement"),
    (2, "Continuous Improvement"),
    (3, "Continuous Improvement"),
    (4, "Innovation"),
    (5, "Innovation"),
    (6, "Innovation"),
    (7, "Invention"),
    (8, "Invention"),
    (9, "Invention"),
    (10, "Invention"),
]


def _independent_book_iq(total: int) -> Decimal:
    """Spec 3.2 by plain integer maths: round half up of total / 120 x 100 to 1 decimal."""
    tenths = (total * 1000 * 2 + 120) // (2 * 120)
    return Decimal(tenths).scaleb(-1)


def _equal(weight: object) -> dict[str, object]:
    return dict.fromkeys(KEYS, weight)


# --- golden examples (spec 11) -----------------------------------------------------------


def test_golden_sum_84_gives_70() -> None:
    result = score_iq(iq_scores([7] * 12))
    assert result.iq == Decimal("70.0")
    assert str(result.iq) == "70.0"


def test_golden_sum_84_any_distribution() -> None:
    result = score_iq(iq_scores([10, 10, 10, 10, 10, 10, 10, 10, 1, 1, 1, 1]))
    assert result.iq == Decimal("70.0")


def test_golden_all_10_gives_100_and_all_1_gives_10() -> None:
    assert str(score_iq(iq_scores([10] * 12)).iq) == "100.0"
    assert str(score_iq(iq_scores([1] * 12)).iq) == "10.0"


@pytest.mark.parametrize(("score", "level_name"), LEVEL_TABLE)
def test_level_table(score: int, level_name: str) -> None:
    assert iq_level(score).name == level_name


@pytest.mark.parametrize(("score", "level_name"), LEVEL_TABLE)
def test_level_on_every_dimension_of_a_result(score: int, level_name: str) -> None:
    result = score_iq(iq_scores([score] * 12))
    assert all(d.level is not None and d.level.name == level_name for d in result.dimensions)


@pytest.mark.parametrize("score", [0, 11, -1])
def test_level_rejects_off_scale(score: int) -> None:
    with pytest.raises(ScoringError, match="1 to 10"):
        iq_level(score)


@pytest.mark.parametrize("value", [0, 11, -3, 5.5, 5.0, True, False, "5", Decimal(5)])
def test_invalid_score_is_rejected(value: Any) -> None:
    scores: dict[str, Any] = iq_scores([5] * 12)
    scores[KEYS[3]] = value
    with pytest.raises(ScoringError, match=KEYS[3]):
        score_iq(scores)


@pytest.mark.parametrize("total", range(12, 121))
def test_book_formula_for_every_possible_sum(total: int) -> None:
    assert score_iq(iq_scores_for_sum(total)).iq == _independent_book_iq(total)


def test_iq_has_exactly_one_decimal() -> None:
    assert str(score_iq(iq_scores_for_sum(83)).iq) == "69.2"
    assert str(score_iq(iq_scores_for_sum(13)).iq) == "10.8"


def test_iq_minimum_is_10_and_maximum_is_100() -> None:
    assert iq_minimum() == Decimal(10)
    assert iq_maximum() == Decimal(100)


# --- partial and unknown input -----------------------------------------------------------


def test_empty_scores_are_incomplete() -> None:
    result = score_iq({})
    assert not result.complete
    assert result.iq is None
    assert all(d.score is None and d.level is None for d in result.dimensions)


@pytest.mark.parametrize("how", ["absent", "none"])
def test_missing_score_gives_no_iq_but_keeps_levels(how: str) -> None:
    scores: dict[str, Any] = iq_scores([8] * 12)
    if how == "absent":
        del scores[KEYS[11]]
    else:
        scores[KEYS[11]] = None
    result = score_iq(scores)
    assert not result.complete
    assert result.iq is None
    assert result.dimensions[11].score is None
    assert result.dimensions[11].level is None
    assert [d.level.name for d in result.dimensions[:11] if d.level] == ["Invention"] * 11


def test_missing_score_with_weights_gives_no_iq() -> None:
    scores = iq_scores([8] * 12)
    del scores[KEYS[0]]
    assert score_iq(scores, weights=_equal(1)).iq is None


def test_unknown_dimension_is_rejected() -> None:
    with pytest.raises(ScoringError, match="Unknown dimension key: 'novelty'"):
        score_iq({**iq_scores([5] * 12), "novelty": 5})


@pytest.mark.parametrize("scores", [[5] * 12, None, "x"])
def test_non_mapping_scores_are_rejected(scores: Any) -> None:
    with pytest.raises(ScoringError, match="mapping"):
        score_iq(scores)


def test_result_shape() -> None:
    result = score_iq(iq_scores([*range(1, 11), 5, 5]))
    assert result.question_set_version == QS.version
    assert tuple(d.key for d in result.dimensions) == QS.dimension_keys
    assert isinstance(result.dimensions, tuple)
    assert result.weights is None
    assert not result.weighted
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.iq = Decimal(1)  # type: ignore[misc]


# --- weights (PROVISIONAL Q2) ------------------------------------------------------------

EQUAL_WEIGHTS = [
    pytest.param(1, id="int 1"),
    pytest.param(7, id="int 7"),
    pytest.param(1000, id="int 1000 (max)"),
    pytest.param(Decimal("0.5"), id="Decimal 0.5"),
    pytest.param(Decimal("0.1"), id="Decimal 0.1"),
    pytest.param(Decimal("0.083333"), id="Decimal 0.083333"),
    pytest.param(Decimal("0.000001"), id="Decimal smallest step"),
]


@pytest.mark.parametrize("weight", EQUAL_WEIGHTS)
def test_equal_weights_reproduce_the_book_formula_for_every_sum(weight: object) -> None:
    for total in range(12, 121):
        scores = iq_scores_for_sum(total)
        assert score_iq(scores, weights=_equal(weight)).iq == score_iq(scores).iq, total


@pytest.mark.parametrize("factor", [Decimal("0.001"), Decimal(3), Decimal(100), Decimal("2.5"), 40])
def test_weights_need_not_sum_to_1_and_scaling_does_not_change_iq(factor: Any) -> None:
    """(2x10 + 1 + 10x5) x 100 / (13 x 10) = 54.61... -> 54.6, whatever the scale."""
    scores = iq_scores([10, 1, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5])
    base = [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    expected = score_iq(scores, weights=dict(zip(KEYS, base, strict=True))).iq
    scaled = {k: w * factor for k, w in zip(KEYS, base, strict=True)}
    assert sum(scaled.values()) != 1
    assert score_iq(scores, weights=scaled).iq == expected == Decimal("54.6")


def test_weighted_formula_hand_example() -> None:
    """Weight 2 on the first dimension: (2x10 + 11x5) x 100 / (13 x 10) = 57.69... -> 57.7."""
    scores = iq_scores([10] + [5] * 11)
    weights = dict(zip(KEYS, [2] + [1] * 11, strict=True))
    result = score_iq(scores, weights=weights)
    assert result.iq == Decimal("57.7")
    assert result.weighted
    assert result.weights == tuple((k, Decimal(w)) for k, w in weights.items())


def test_weights_summing_to_1_give_the_same_iq() -> None:
    """0.12 on the first dimension and 0.08 on each other one (sum exactly 1) is 3 : 2."""
    scores = iq_scores([10] + [5] * 11)
    weights = dict(zip(KEYS, [Decimal("0.12")] + [Decimal("0.08")] * 11, strict=True))
    assert sum(weights.values()) == 1
    assert (
        score_iq(scores, weights=weights).iq
        == score_iq(scores, weights=dict(zip(KEYS, [3] + [2] * 11, strict=True))).iq
        == Decimal("56.0")
    )


def test_zero_weight_ignores_a_dimension() -> None:
    scores = iq_scores([3] + [10] * 11)
    weights = {k: (1 if i == 0 else 0) for i, k in enumerate(KEYS)}
    assert score_iq(scores, weights=weights).iq == Decimal("30.0")


def test_weighted_iq_rounds_half_up() -> None:
    """(2 + 199 x 1) x 100 / (200 x 10) = 10.05 exactly, shown as 10.1 (PROVISIONAL Q18)."""
    scores = iq_scores([2, 1] + [1] * 10)
    weights = {k: (1 if i == 0 else 199 if i == 1 else 0) for i, k in enumerate(KEYS)}
    assert score_iq(scores, weights=weights).iq == Decimal("10.1")


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        pytest.param(-1, "must be 0 to 1000", id="negative int"),
        pytest.param(Decimal("-0.1"), "must be 0 to 1000", id="negative Decimal"),
        pytest.param(1001, "must be 0 to 1000", id="int above max"),
        pytest.param(Decimal("1000.000001"), "must be 0 to 1000", id="Decimal above max"),
        pytest.param(Decimal("0.0000001"), "at most 6 decimal places", id="7 decimal places"),
        pytest.param(Decimal("1.0000001"), "at most 6 decimal places", id="7 places above 1"),
        pytest.param(Decimal("1E-999999"), "at most 6 decimal places", id="tiny exponent"),
        pytest.param(0.5, "not a float", id="float"),
        pytest.param(1.0, "not a float", id="whole float"),
        pytest.param(math.nan, "not a float", id="nan"),
        pytest.param(math.inf, "not a float", id="inf"),
        pytest.param(Decimal("NaN"), "finite", id="Decimal NaN"),
        pytest.param(Decimal("sNaN"), "finite", id="Decimal sNaN"),
        pytest.param(Decimal("Infinity"), "finite", id="Decimal inf"),
        pytest.param(True, "must be a number", id="bool"),
        pytest.param("1", "must be a number", id="text"),
        pytest.param(None, "must be a number", id="None"),
        pytest.param(Fraction(1, 2), "must be a number", id="Fraction"),
    ],
)
def test_invalid_weight_is_rejected(bad: object, message: str) -> None:
    weights = _equal(1)
    weights[KEYS[4]] = bad
    with pytest.raises(ScoringError, match=message):
        score_iq(iq_scores([5] * 12), weights=weights)


@pytest.mark.parametrize(
    "weight", [0, 1000, Decimal("1000.000000"), Decimal("0.000001"), Decimal("12.345678")]
)
def test_weight_bounds_are_accepted(weight: object) -> None:
    weights = _equal(1)
    weights[KEYS[0]] = weight
    assert score_iq(iq_scores([5] * 12), weights=weights).iq == Decimal("50.0")


@pytest.mark.parametrize(
    "huge",
    [
        pytest.param(Decimal("1E10000000"), id="Decimal 1E10000000"),
        pytest.param(Decimal("1E+999999"), id="Decimal 1E+999999"),
        pytest.param(10**100_000, id="int with 100001 digits"),
    ],
)
def test_huge_weight_is_rejected_fast(huge: object) -> None:
    weights = _equal(1)
    weights[KEYS[0]] = huge
    start = time.perf_counter()
    with pytest.raises(ScoringError, match="must be 0 to 1000"):
        score_iq(iq_scores([5] * 12), weights=weights)
    assert time.perf_counter() - start < 0.5


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        (Decimal("-0"), "0"),
        (Decimal("0E+3"), "0"),
        (Decimal("1E+3"), "1000"),
        (Decimal("2.500000"), "2.5"),
        (Decimal("5E-6"), "0.000005"),
        (7, "7"),
    ],
)
def test_stored_weights_are_normalised(given: object, stored: str) -> None:
    weights = _equal(1)
    weights[KEYS[0]] = given
    result = score_iq(iq_scores([5] * 12), weights=weights)
    assert result.weights is not None
    assert str(result.weights[0][1]) == stored
    assert [str(w) for _, w in result.weights[1:]] == ["1"] * 11


@pytest.mark.parametrize("zero", [0, Decimal(0), Decimal("-0"), Decimal("0.000")])
def test_all_zero_weights_are_rejected(zero: object) -> None:
    with pytest.raises(ScoringError, match="above zero"):
        score_iq(iq_scores([5] * 12), weights=_equal(zero))


def test_weights_missing_a_dimension_are_rejected() -> None:
    weights = _equal(1)
    del weights[KEYS[2]]
    with pytest.raises(ScoringError, match=f"missing for dimensions: \\['{KEYS[2]}'\\]"):
        score_iq(iq_scores([5] * 12), weights=weights)


def test_weights_with_unknown_dimension_are_rejected() -> None:
    with pytest.raises(ScoringError, match="Unknown dimension keys in weights"):
        score_iq(iq_scores([5] * 12), weights={**_equal(1), "risk": 1})


def test_weights_must_be_a_mapping() -> None:
    with pytest.raises(ScoringError, match="mapping"):
        score_iq(iq_scores([5] * 12), weights=[1] * 12)  # type: ignore[arg-type]


def test_invalid_weights_are_rejected_even_when_incomplete() -> None:
    with pytest.raises(ScoringError, match="above zero"):
        score_iq({}, weights=_equal(0))


def test_weight_limits_constant() -> None:
    assert (WEIGHT_LIMITS.minimum, WEIGHT_LIMITS.maximum) == (0, 1000)
    assert WEIGHT_LIMITS.max_decimal_places == 6


# --- public surface ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["book_iq", "weighted_iq", "validated_weights", "compute_iq", "calculate_iq", "iq_formula"],
)
def test_old_public_formula_names_are_absent(name: str) -> None:
    assert not hasattr(iq_module, name)


def test_raw_formula_helpers_are_private() -> None:
    public = {n for n in vars(iq_module) if not n.startswith("_") and callable(vars(iq_module)[n])}
    functions = {
        n for n in public if getattr(vars(iq_module)[n], "__module__", "") == iq_module.__name__
    }
    assert functions == {
        "score_iq",
        "iq_level",
        "iq_minimum",
        "iq_maximum",
        "DimensionIq",
        "IqResult",
        "WeightLimits",
    }
