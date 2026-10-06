"""Priorities (spec section 7 and the priorities golden example in section 11)."""

import dataclasses
from pathlib import Path

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


def test_iq_priorities_ignore_weights() -> None:
    scores = iq_scores([10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 10])
    weights = dict(zip(KEYS, range(1, 13), strict=True))
    assert iq_priorities(score_iq(scores, weights=weights)) == iq_priorities(score_iq(scores))


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
        readiness_priorities(score_readiness(all_answers(3)), other)
    with pytest.raises(ScoringError, match="question_set_version"):
        iq_priorities(score_iq(iq_scores([5] * 12)), other)


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


def test_tie_break_carries_the_q19_marker() -> None:
    source = Path(priorities_module.__file__).read_text(encoding="utf-8")
    assert "key=lambda row: (row[3], row[2]),  # PROVISIONAL: see open-questions Q19" in source
