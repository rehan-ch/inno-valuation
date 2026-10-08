"""Innovation Quotient (spec section 3 and the IQ golden examples in section 11)."""

import dataclasses
import inspect
from decimal import Decimal
from typing import Any

import pytest

import app.scoring.iq as iq_module
from app.scoring.errors import ScoringError
from app.scoring.iq import iq_level, iq_maximum, iq_minimum, score_iq
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
    assert [f.name for f in dataclasses.fields(result)] == [
        "question_set_version",
        "dimensions",
        "iq",
    ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.iq = Decimal(1)  # type: ignore[misc]


# --- weights never change the IQ (spec 3.4, golden example in spec 11) -------------------


def test_golden_weights_never_change_the_iq_score_iq_has_no_weights_parameter() -> None:
    """Spec 11: any set of weights gives the same IQ as the book formula (Q2).

    The IQ cannot take weights at all; weights live only in priorities (spec 7). The
    priorities side of this golden example is in test_priorities.py.
    """
    parameters = inspect.signature(score_iq).parameters
    assert list(parameters) == ["scores", "question_set"]
    assert parameters["question_set"].kind is inspect.Parameter.KEYWORD_ONLY


def test_passing_weights_to_score_iq_fails_loudly() -> None:
    """mypy already rejects these calls; at run time they raise TypeError, never ignore."""
    untyped: Any = score_iq
    with pytest.raises(TypeError, match="weights"):
        untyped(iq_scores([5] * 12), weights=dict.fromkeys(KEYS, 1))
    with pytest.raises(TypeError, match="positional"):
        untyped(iq_scores([5] * 12), dict.fromkeys(KEYS, 1))


# --- public surface ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "book_iq",
        "weighted_iq",
        "_weighted_iq",
        "validated_weights",
        "_validated_weights",
        "WEIGHT_LIMITS",
        "WeightLimits",
        "compute_iq",
        "calculate_iq",
        "iq_formula",
    ],
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
    }
