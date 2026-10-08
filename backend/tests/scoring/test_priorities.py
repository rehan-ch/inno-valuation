"""Priorities (spec section 7 and the priorities golden example in section 11)."""

import dataclasses
import inspect
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import app.scoring.priorities as priorities_module
from app.scoring.errors import ScoringError
from app.scoring.iq import score_iq
from app.scoring.priorities import PRIORITY_COUNT, iq_priorities, readiness_priorities
from app.scoring.readiness import score_readiness
from tests.scoring.support import (
    KEYS,
    QS,
    all_answers,
    answers_for_dimension_scores,
    iq_scores,
)


def _readiness(scores: list[int]):  # type: ignore[no-untyped-def]
    return score_readiness(answers_for_dimension_scores(scores))


def test_priority_count_is_5() -> None:
    assert PRIORITY_COUNT == 5


def test_golden_readiness_25_to_14_gives_dimensions_12_11_10_9_8() -> None:
    result = readiness_priorities(_readiness(list(range(25, 13, -1))))
    assert [item.rank for item in result.items] == [1, 2, 3, 4, 5]
    assert [QS.dimension(item.key).order for item in result.items] == [12, 11, 10, 9, 8]
    assert [item.score for item in result.items] == [14, 15, 16, 17, 18]
    assert [item.name for item in result.items] == [
        QS.dimensions[i].name for i in (11, 10, 9, 8, 7)
    ]
    assert result.question_set_version == QS.version


@pytest.mark.parametrize(
    ("scores", "expected_orders"),
    [
        pytest.param([15] * 12, [1, 2, 3, 4, 5], id="all tied: book order"),
        pytest.param(
            [20, 10, 20, 10, 20, 10, 20, 10, 20, 10, 20, 10], [2, 4, 6, 8, 10], id="tie at lowest"
        ),
        pytest.param(
            [5, 25, 25, 25, 25, 25, 25, 25, 9, 9, 9, 9], [1, 9, 10, 11, 12], id="tie across cut"
        ),
        pytest.param(
            [25, 25, 25, 25, 25, 25, 25, 7, 7, 7, 7, 6], [12, 8, 9, 10, 11], id="lowest then ties"
        ),
    ],
)
def test_ties_break_by_book_order(scores: list[int], expected_orders: list[int]) -> None:
    result = readiness_priorities(_readiness(scores))
    assert [QS.dimension(item.key).order for item in result.items] == expected_orders


def test_iq_priorities() -> None:
    result = iq_priorities(score_iq(iq_scores([10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 10])))
    assert [item.key for item in result.items] == [KEYS[9], KEYS[10], KEYS[8], KEYS[7], KEYS[6]]
    assert [item.score for item in result.items] == [1, 1, 2, 3, 4]


def test_incomplete_readiness_is_rejected() -> None:
    with pytest.raises(ScoringError, match="complete result"):
        readiness_priorities(score_readiness({}))


def test_incomplete_iq_is_rejected() -> None:
    scores = iq_scores([5] * 12)
    del scores[KEYS[0]]
    with pytest.raises(ScoringError, match="complete result"):
        iq_priorities(score_iq(scores))


def test_other_question_set_version_is_rejected() -> None:
    other = dataclasses.replace(QS, version=QS.version + 1)
    with pytest.raises(ScoringError, match="question_set_version"):
        readiness_priorities(score_readiness(all_answers(3)), question_set=other)
    with pytest.raises(ScoringError, match="question_set_version"):
        iq_priorities(score_iq(iq_scores([5] * 12)), question_set=other)


def test_result_with_foreign_dimensions_is_rejected() -> None:
    result = score_readiness(all_answers(3))
    tampered = dataclasses.replace(result, dimensions=result.dimensions[::-1])
    with pytest.raises(ScoringError, match="do not match"):
        readiness_priorities(tampered)


def test_result_is_frozen_tuple() -> None:
    result = readiness_priorities(score_readiness(all_answers(3)))
    assert isinstance(result.items, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.items[0].rank = 9  # type: ignore[misc]


def test_tie_break_markers() -> None:
    source = Path(priorities_module.__file__).read_text(encoding="utf-8")
    assert "-row.weight,  # PROVISIONAL: see open-questions Q23" in source
    assert "row.order,  # PROVISIONAL: see open-questions Q19" in source


# --- weights reorder priorities (spec 7; how: PROVISIONAL Q23) -------------------------------

BRAND = KEYS[1]  # book order 2
DATA = KEYS[10]  # book order 11
IQ_TIE = [9, 3, 9, 9, 9, 9, 9, 9, 9, 9, 3, 9]  # Brand and Data both 3
READINESS_TIE = [25, 8, 25, 25, 25, 25, 25, 25, 25, 25, 8, 25]


def _weights(**overrides: object) -> dict[str, object]:
    weights: dict[str, object] = dict.fromkeys(KEYS, 1)
    for index, value in overrides.items():
        weights[KEYS[int(index.removeprefix("d"))]] = value
    return weights


def test_question_set_is_keyword_only() -> None:
    for function in (readiness_priorities, iq_priorities):
        parameters = inspect.signature(function).parameters
        assert list(parameters) == ["result", "weights", "question_set"]
        assert parameters["weights"].default is None
        assert parameters["question_set"].kind is inspect.Parameter.KEYWORD_ONLY


def test_iq_weight_breaks_a_tie() -> None:
    """Brand and Data both score 3. Without weights Brand comes first (book order)."""
    result = score_iq(iq_scores(IQ_TIE))
    assert [i.key for i in iq_priorities(result).items[:2]] == [BRAND, DATA]
    weighted = iq_priorities(result, _weights(d10=Decimal("1.5")))
    assert [i.key for i in weighted.items[:2]] == [DATA, BRAND]
    assert [i.rank for i in weighted.items] == [1, 2, 3, 4, 5]


def test_readiness_weight_breaks_a_tie() -> None:
    result = score_readiness(answers_for_dimension_scores(READINESS_TIE))
    assert [i.key for i in readiness_priorities(result).items[:2]] == [BRAND, DATA]
    weighted = readiness_priorities(result, _weights(d10=2))
    assert [i.key for i in weighted.items[:2]] == [DATA, BRAND]


def test_smallest_weight_step_breaks_a_tie() -> None:
    result = score_iq(iq_scores(IQ_TIE))
    weights = _weights(d1=Decimal("12.345677"), d10=Decimal("12.345678"))
    assert [i.key for i in iq_priorities(result, weights).items[:2]] == [DATA, BRAND]


def test_weight_reorders_the_rest_of_a_tie_group() -> None:
    """All tied at 9 after the two 3s: the heavier 9s come first, then book order."""
    result = score_iq(iq_scores(IQ_TIE))
    weights = _weights(d11=5, d9=4, d0=4)
    keys = [i.key for i in iq_priorities(result, weights).items]
    assert keys == [BRAND, DATA, KEYS[11], KEYS[0], KEYS[9]]


@pytest.mark.parametrize(
    "weight",
    [1, 7, 1000, Decimal("0.5"), Decimal("0.000001"), Decimal("1000.000000")],
)
@pytest.mark.parametrize(
    "scores",
    [
        pytest.param([15] * 12, id="all tied"),
        pytest.param([20, 10, 20, 10, 20, 10, 20, 10, 20, 10, 20, 10], id="tie at lowest"),
        pytest.param([5, 25, 25, 25, 25, 25, 25, 25, 9, 9, 9, 9], id="tie across cut"),
        pytest.param(list(range(25, 13, -1)), id="golden"),
    ],
)
def test_equal_weights_and_none_give_the_old_order(weight: object, scores: list[int]) -> None:
    result = _readiness(scores)
    old = readiness_priorities(result)
    assert readiness_priorities(result, dict.fromkeys(KEYS, weight)) == old
    iq_result = score_iq(iq_scores([max(1, s // 3) for s in scores]))
    assert iq_priorities(iq_result, dict.fromkeys(KEYS, weight)) == iq_priorities(iq_result)


def test_golden_example_is_unchanged_by_weights_on_distinct_scores() -> None:
    """Distinct scores: no ties, so no weight can change the order (Q23 provisional)."""
    result = _readiness(list(range(25, 13, -1)))
    heavy_first = dict(zip(KEYS, range(1000, 988, -1), strict=True))
    heavy_last = dict(zip(KEYS, range(1, 13), strict=True))
    for weights in (heavy_first, heavy_last):
        orders = [QS.dimension(i.key).order for i in readiness_priorities(result, weights).items]
        assert orders == [12, 11, 10, 9, 8]


def test_lower_score_always_beats_a_higher_weight() -> None:
    """Data scores 2 with weight 0; Brand scores 3 with weight 1000. Data still comes first."""
    scores = [9, 3, 9, 9, 9, 9, 9, 9, 9, 9, 2, 9]
    weights = _weights(d1=1000, d10=0)
    keys = [i.key for i in iq_priorities(score_iq(iq_scores(scores)), weights).items[:2]]
    assert keys == [DATA, BRAND]


def test_zero_weight_dimension_goes_last_within_its_tie() -> None:
    result = score_iq(iq_scores([4] * 12))
    weights = _weights(d0=0)
    keys = [i.key for i in iq_priorities(result, weights).items]
    assert keys == list(KEYS[1:6])


WEIGHT_SETS = [
    pytest.param(dict(zip(KEYS, range(1, 13), strict=True)), id="1 to 12"),
    pytest.param(dict(zip(KEYS, range(12, 0, -1), strict=True)), id="12 to 1"),
    pytest.param(_weights(d0=0), id="one zero"),
    pytest.param(_weights(d10=1000), id="one max"),
    pytest.param({k: Decimal("0.000001") * (i + 1) for i, k in enumerate(KEYS)}, id="tiny"),
    pytest.param(dict.fromkeys(KEYS, Decimal("0.083333")), id="equal, sum not 1"),
]


@pytest.mark.parametrize("weights", WEIGHT_SETS)
def test_golden_weights_never_change_the_iq_or_any_score(weights: dict[str, Any]) -> None:
    """Spec 11 golden example (Q2): weights never change the IQ. Spec 7: only the order.

    score_iq has no weights parameter (test_iq.py). Here: priorities with any valid
    weights leave the IQ, every dimension score and every shown priority score unchanged.
    """
    scores = iq_scores([7, 3, 9, 3, 5, 3, 4, 8, 6, 10, 3, 7])
    result = score_iq(scores)
    plain = iq_priorities(result)
    weighted = iq_priorities(result, weights)
    assert result == score_iq(scores)
    assert result.iq == Decimal("56.7")  # 68 / 120 x 100, the book formula
    by_key = {d.key: d.score for d in result.dimensions}
    assert all(item.score == by_key[item.key] for item in weighted.items)
    assert [i.score for i in weighted.items] == [i.score for i in plain.items]

    readiness_scores = [20, 8, 25, 8, 15, 8, 12, 22, 18, 25, 8, 14]
    readiness = _readiness(readiness_scores)
    ranked = readiness_priorities(readiness, weights)
    assert readiness == _readiness(readiness_scores)
    assert readiness.total == 183
    by_key_r = {d.key: d.score for d in readiness.dimensions}
    assert all(item.score == by_key_r[item.key] for item in ranked.items)
    assert [i.score for i in ranked.items] == [
        i.score for i in readiness_priorities(readiness).items
    ]


def test_weights_are_validated_before_the_completeness_check() -> None:
    with pytest.raises(ScoringError, match="above zero"):
        iq_priorities(score_iq({}), dict.fromkeys(KEYS, 0))


def test_valid_weights_do_not_hide_an_incomplete_result() -> None:
    with pytest.raises(ScoringError, match="complete result"):
        readiness_priorities(score_readiness({}), dict.fromkeys(KEYS, 1))
