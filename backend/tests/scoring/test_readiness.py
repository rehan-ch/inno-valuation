"""Innovation Readiness (spec section 2 and the readiness golden examples in section 11)."""

import dataclasses
from decimal import Decimal
from typing import Any

import pytest

from app.scoring.errors import ScoringError
from app.scoring.readiness import readiness_band, score_readiness, validate_answers
from tests.scoring.support import QS, all_answers, answers_for_total

CJ = "customer_journey"

# (total, band name) per spec 2.4: one below, on and one above every boundary.
BAND_TABLE = [
    (60, "Beginner"),
    (61, "Beginner"),
    (98, "Beginner"),
    (99, "Beginner"),
    (100, "Emerging Innovator"),
    (101, "Emerging Innovator"),
    (173, "Emerging Innovator"),
    (174, "Emerging Innovator"),
    (175, "Building Blocks"),
    (176, "Building Blocks"),
    (248, "Building Blocks"),
    (249, "Building Blocks"),
    (250, "Innovation Champion"),
    (251, "Innovation Champion"),
    (299, "Innovation Champion"),
    (300, "Innovation Champion"),
]


# --- golden examples (spec 11) -----------------------------------------------------------


def test_golden_customer_journey_4_3_5_4_4_scores_20() -> None:
    ids = QS.question_ids(CJ)
    result = score_readiness(dict(zip(ids, [4, 3, 5, 4, 4], strict=True)))
    assert result.dimensions[0].key == CJ
    assert result.dimensions[0].score == 20
    assert not result.complete


def test_golden_all_5_gives_300_innovation_champion() -> None:
    result = score_readiness(all_answers(5))
    assert result.complete
    assert result.total == 300
    assert result.band is not None
    assert result.band.name == "Innovation Champion"
    assert all(d.score == 25 for d in result.dimensions)


def test_golden_all_1_gives_60_beginner() -> None:
    result = score_readiness(all_answers(1))
    assert result.total == 60
    assert result.band is not None
    assert result.band.name == "Beginner"
    assert all(d.score == 5 for d in result.dimensions)


# --- bands -------------------------------------------------------------------------------


@pytest.mark.parametrize(("total", "band_name"), BAND_TABLE)
def test_band_boundaries_via_answers(total: int, band_name: str) -> None:
    result = score_readiness(answers_for_total(total))
    assert result.total == total
    assert result.band is not None
    assert result.band.name == band_name


@pytest.mark.parametrize(("total", "band_name"), BAND_TABLE)
def test_band_boundaries_via_lookup(total: int, band_name: str) -> None:
    assert readiness_band(total).name == band_name


def test_band_key_and_text_come_from_the_yml() -> None:
    expected = {b.name: b for b in QS.readiness_bands}
    for total, name in BAND_TABLE:
        assert readiness_band(total) == expected[name]
    band = readiness_band(250)
    assert band.key == "innovation_champion"
    assert band.text == (
        "Your organization is thriving in innovation across all dimensions. "
        "Maintain momentum and fine-tune strategies."
    )


@pytest.mark.parametrize("total", [59, 301, 0, -1, 99_999])
def test_band_rejects_impossible_totals(total: int) -> None:
    with pytest.raises(ScoringError, match="60 to 300"):
        readiness_band(total)


@pytest.mark.parametrize("total", [100.0, True, "100", Decimal(100), None])
def test_band_rejects_non_integer_totals(total: Any) -> None:
    with pytest.raises(ScoringError, match="integer"):
        readiness_band(total)


# --- invalid answers ---------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 6, -1, 3.5, 4.0, True, False, "4", Decimal(4), [4]])
def test_invalid_answer_is_rejected(value: Any) -> None:
    answers: dict[str, Any] = all_answers(3)
    first_id = QS.all_question_ids()[7]
    answers[first_id] = value
    with pytest.raises(ScoringError, match=first_id):
        score_readiness(answers)


@pytest.mark.parametrize("value", [1, 2, 3, 4, 5])
def test_every_scale_value_is_accepted(value: int) -> None:
    assert score_readiness(all_answers(value)).total == 60 * value


def test_unknown_question_id_is_rejected() -> None:
    with pytest.raises(ScoringError, match="Unknown question id: 'leadership_1'"):
        score_readiness({**all_answers(3), "leadership_1": 3})


@pytest.mark.parametrize("answers", [[3] * 60, "x", None, 3])
def test_non_mapping_answers_are_rejected(answers: Any) -> None:
    with pytest.raises(ScoringError, match="mapping"):
        score_readiness(answers)


def test_non_text_question_id_is_rejected() -> None:
    bad: dict[Any, int] = {1: 3}
    with pytest.raises(ScoringError, match="must be text"):
        score_readiness(bad)


def test_validate_answers_returns_only_answered_questions() -> None:
    ids = QS.all_question_ids()
    assert validate_answers({ids[0]: 2, ids[1]: None}) == {ids[0]: 2}
    assert validate_answers({}) == {}


# --- empty and partial input -------------------------------------------------------------


def test_empty_answers_are_incomplete_never_zero() -> None:
    result = score_readiness({})
    assert not result.complete
    assert result.total is None
    assert result.band is None
    assert all(d.score is None and d.answered == 0 for d in result.dimensions)
    assert result.missing_question_ids == QS.all_question_ids()


@pytest.mark.parametrize("how", ["absent", "none"])
def test_one_missing_answer_makes_the_result_incomplete(how: str) -> None:
    answers: dict[str, Any] = all_answers(4)
    missing = QS.question_ids(QS.dimension_keys[5])[2]
    if how == "absent":
        del answers[missing]
    else:
        answers[missing] = None
    result = score_readiness(answers)
    assert not result.complete
    assert result.total is None
    assert result.band is None
    assert result.missing_question_ids == (missing,)
    assert result.dimensions[5].score is None
    assert result.dimensions[5].answered == 4
    assert [d.score for i, d in enumerate(result.dimensions) if i != 5] == [20] * 11


# --- shape -------------------------------------------------------------------------------


def test_result_is_frozen_in_book_order_with_version() -> None:
    result = score_readiness(all_answers(2))
    assert result.question_set_version == QS.version
    assert tuple(d.key for d in result.dimensions) == QS.dimension_keys
    assert tuple(d.name for d in result.dimensions) == tuple(d.name for d in QS.dimensions)
    assert isinstance(result.dimensions, tuple)
    assert isinstance(result.missing_question_ids, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.total = 1  # type: ignore[misc]


def test_answer_order_does_not_matter() -> None:
    answers = answers_for_total(187)
    reversed_answers = dict(reversed(list(answers.items())))
    assert score_readiness(reversed_answers) == score_readiness(answers)


def test_result_has_no_per_dimension_label() -> None:
    """Spec 2.5 / Q4: no per-dimension status labels until Amy decides."""
    fields = {f.name for f in dataclasses.fields(score_readiness({}).dimensions[0])}
    assert fields == {"key", "name", "order", "category", "score", "answered"}


def test_huge_answer_gives_a_short_scoring_error() -> None:
    answers: dict[str, Any] = all_answers(3)
    answers[QS.all_question_ids()[0]] = 10**10_000
    with pytest.raises(ScoringError, match="too large to show"):
        score_readiness(answers)
