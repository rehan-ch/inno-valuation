"""Client weights validation (spec 3.4 and 7; limits PROVISIONAL Q22)."""

import inspect
import math
import time
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

import app.scoring.weights as weights_module
from app.scoring.errors import ScoringError
from app.scoring.iq import score_iq
from app.scoring.priorities import PriorityResult, iq_priorities, readiness_priorities
from app.scoring.readiness import score_readiness
from app.scoring.weights import WEIGHT_LIMITS, validate_weights
from tests.scoring.support import KEYS, all_answers, iq_scores


def _equal(weight: object) -> dict[str, object]:
    return dict.fromkeys(KEYS, weight)


def _via_iq(weights: Any) -> PriorityResult:
    return iq_priorities(score_iq(iq_scores([5] * 12)), weights)


def _via_readiness(weights: Any) -> PriorityResult:
    return readiness_priorities(score_readiness(all_answers(3)), weights)


ENTRY_POINTS = [
    pytest.param(_via_iq, id="iq_priorities"),
    pytest.param(_via_readiness, id="readiness_priorities"),
]

Entry = Callable[[Any], PriorityResult]


def test_weight_limits_constant() -> None:
    assert (WEIGHT_LIMITS.minimum, WEIGHT_LIMITS.maximum) == (0, 1000)
    assert WEIGHT_LIMITS.max_decimal_places == 6


@pytest.mark.parametrize("entry", ENTRY_POINTS)
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
def test_invalid_weight_is_rejected(entry: Entry, bad: object, message: str) -> None:
    weights = _equal(1)
    weights[KEYS[4]] = bad
    with pytest.raises(ScoringError, match=message):
        entry(weights)


@pytest.mark.parametrize("entry", ENTRY_POINTS)
@pytest.mark.parametrize(
    "huge",
    [
        pytest.param(Decimal("1E10000000"), id="Decimal 1E10000000"),
        pytest.param(Decimal("1E+999999"), id="Decimal 1E+999999"),
        pytest.param(10**100_000, id="int with 100001 digits"),
    ],
)
def test_huge_weight_is_rejected_fast(entry: Entry, huge: object) -> None:
    weights = _equal(1)
    weights[KEYS[0]] = huge
    start = time.perf_counter()
    with pytest.raises(ScoringError, match="must be 0 to 1000"):
        entry(weights)
    assert time.perf_counter() - start < 0.5


@pytest.mark.parametrize("entry", ENTRY_POINTS)
@pytest.mark.parametrize("zero", [0, Decimal(0), Decimal("-0"), Decimal("0.000")])
def test_all_zero_weights_are_rejected(entry: Entry, zero: object) -> None:
    with pytest.raises(ScoringError, match="above zero"):
        entry(_equal(zero))


@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_weights_missing_a_dimension_are_rejected(entry: Entry) -> None:
    weights = _equal(1)
    del weights[KEYS[2]]
    with pytest.raises(ScoringError, match=f"missing for dimensions: \\['{KEYS[2]}'\\]"):
        entry(weights)


@pytest.mark.parametrize("entry", ENTRY_POINTS)
@pytest.mark.parametrize(
    "extra",
    [
        pytest.param("risk", id="text"),
        pytest.param(7, id="int"),
        pytest.param(10**100_000, id="huge int"),
    ],
)
def test_weights_with_unknown_dimension_are_rejected(entry: Entry, extra: object) -> None:
    with pytest.raises(ScoringError, match="Unknown dimension keys in weights"):
        entry({**_equal(1), extra: 1})


@pytest.mark.parametrize("entry", ENTRY_POINTS)
@pytest.mark.parametrize(
    "bad",
    [pytest.param([1] * 12, id="list"), pytest.param("x", id="text"), pytest.param(1, id="int")],
)
def test_weights_must_be_a_mapping(entry: Entry, bad: object) -> None:
    with pytest.raises(ScoringError, match="mapping"):
        entry(bad)


@pytest.mark.parametrize(
    "weight", [0, 1000, Decimal("1000.000000"), Decimal("0.000001"), Decimal("12.345678")]
)
def test_weight_bounds_are_accepted(weight: object) -> None:
    weights = _equal(1)
    weights[KEYS[0]] = weight
    assert validate_weights(weights)[KEYS[0]] == weight
    assert len(_via_iq(weights).items) == 5


def test_weights_need_not_sum_to_1() -> None:
    weights = dict(zip(KEYS, range(1, 13), strict=True))
    assert sum(weights.values()) == 78
    assert list(validate_weights(weights).values()) == [Decimal(w) for w in range(1, 13)]


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
def test_validated_weights_are_normalised(given: object, stored: str) -> None:
    weights = _equal(1)
    weights[KEYS[0]] = given
    valid = validate_weights(weights)
    assert str(valid[KEYS[0]]) == stored
    assert all(isinstance(w, Decimal) for w in valid.values())
    assert [str(valid[k]) for k in KEYS[1:]] == ["1"] * 11


def test_validated_weights_are_in_book_order() -> None:
    reversed_input = dict.fromkeys(reversed(KEYS), 1)
    assert tuple(validate_weights(reversed_input)) == KEYS


def test_weights_module_does_no_score_arithmetic() -> None:
    """Spec 3.4: weights change no score, so this module exposes only validation."""
    public = {
        n
        for n, v in vars(weights_module).items()
        if not n.startswith("_")
        and callable(v)
        and getattr(v, "__module__", "") == weights_module.__name__
    }
    assert public == {"WeightLimits", "validate_weights"}


def test_snapshot_is_read_only_and_revalidates_to_equal_values() -> None:
    """Spec 3.4: the validated output is stored as the snapshot and passed back later."""
    snapshot = validate_weights(dict(zip(KEYS, [Decimal("2.500000"), *range(1, 12)], strict=True)))
    again = validate_weights(snapshot)
    assert dict(again) == dict(snapshot)
    assert tuple(again) == KEYS
    assert iq_priorities(score_iq(iq_scores([5] * 12)), snapshot) == _via_iq(again)
    with pytest.raises(TypeError):
        snapshot[KEYS[0]] = Decimal(9)  # type: ignore[index]
    with pytest.raises(TypeError):
        del snapshot[KEYS[0]]  # type: ignore[attr-defined]


def test_question_set_is_keyword_only() -> None:
    parameter = inspect.signature(validate_weights).parameters["question_set"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
