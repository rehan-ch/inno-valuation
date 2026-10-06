"""Category aggregates (spec 2.6 and 3.6, PROVISIONAL Q9, Q18, Q20)."""

import dataclasses
from decimal import Decimal

import pytest

from app.scoring.categories import iq_categories, readiness_categories
from app.scoring.errors import ScoringError
from app.scoring.iq import score_iq
from app.scoring.readiness import score_readiness
from tests.scoring.support import (
    KEYS,
    QS,
    all_answers,
    answers_for_dimension_scores,
    iq_scores,
)


def test_readiness_maxima_are_125_50_125_from_the_yml() -> None:
    result = readiness_categories(score_readiness(all_answers(5)))
    assert [c.key for c in result.categories] == [c.key for c in QS.categories]
    assert [c.name for c in result.categories] == [c.name for c in QS.categories]
    assert [c.maximum for c in result.categories] == [125, 50, 125]
    assert [c.score for c in result.categories] == [125, 50, 125]


def test_readiness_category_is_the_sum_of_its_dimensions() -> None:
    scores = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    result = readiness_categories(score_readiness(answers_for_dimension_scores(scores)))
    assert [c.score for c in result.categories] == [35, 21, 70]
    assert result.categories[1].dimension_keys == (KEYS[5], KEYS[6])
    assert result.question_set_version == QS.version


def test_readiness_incomplete_category_is_none() -> None:
    answers = all_answers(4)
    del answers[QS.question_ids(KEYS[6])[0]]
    result = readiness_categories(score_readiness(answers))
    assert [c.score for c in result.categories] == [100, None, 100]


def test_readiness_empty_answers() -> None:
    result = readiness_categories(score_readiness({}))
    assert all(c.score is None for c in result.categories)


def test_iq_category_is_mean_times_ten_with_one_decimal() -> None:
    scores = iq_scores([7, 8, 6, 9, 5, 3, 4, 1, 1, 1, 1, 2])
    result = iq_categories(score_iq(scores))
    assert [str(c.score) for c in result.categories] == ["70.0", "35.0", "12.0"]
    assert [c.maximum for c in result.categories] == [Decimal(100)] * 3
    assert [c.name for c in result.categories] == [c.name for c in QS.categories]


def test_iq_categories_at_the_extremes() -> None:
    assert [c.score for c in iq_categories(score_iq(iq_scores([10] * 12))).categories] == [
        Decimal("100.0")
    ] * 3
    assert [c.score for c in iq_categories(score_iq(iq_scores([1] * 12))).categories] == [
        Decimal("10.0")
    ] * 3


def test_iq_categories_ignore_custom_weights() -> None:
    """PROVISIONAL Q20: weights do not apply inside a category."""
    scores = iq_scores([7, 8, 6, 9, 5, 3, 4, 1, 1, 1, 1, 2])
    weights = dict(zip(KEYS, [9, 1, 1, 1, 1, 5, 1, 1, 1, 1, 1, 9], strict=True))
    weighted = score_iq(scores, weights=weights)
    assert weighted.iq != score_iq(scores).iq
    assert iq_categories(weighted).categories == iq_categories(score_iq(scores)).categories


def test_iq_incomplete_category_is_none() -> None:
    scores = iq_scores([5] * 12)
    del scores[KEYS[0]]
    result = iq_categories(score_iq(scores))
    assert [c.score for c in result.categories] == [None, Decimal("50.0"), Decimal("50.0")]


def test_other_question_set_version_is_rejected() -> None:
    other = dataclasses.replace(QS, version=QS.version + 1)
    with pytest.raises(ScoringError, match="question_set_version"):
        readiness_categories(score_readiness(all_answers(3)), other)
    with pytest.raises(ScoringError, match="question_set_version"):
        iq_categories(score_iq(iq_scores([5] * 12)), other)


def test_results_are_frozen_tuples() -> None:
    result = iq_categories(score_iq(iq_scores([5] * 12)))
    assert isinstance(result.categories, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.categories[0].score = None  # type: ignore[misc]
