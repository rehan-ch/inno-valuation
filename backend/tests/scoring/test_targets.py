"""Targets and gaps (spec section 6, PROVISIONAL Q8)."""

import dataclasses
from decimal import Decimal
from typing import Any

import pytest

from app.scoring.errors import ScoringError
from app.scoring.iq import score_iq
from app.scoring.readiness import score_readiness
from app.scoring.targets import iq_targets, readiness_targets
from tests.scoring.support import KEYS, QS, all_answers, iq_scores


def test_readiness_gap_is_target_minus_current() -> None:
    result = readiness_targets(score_readiness(all_answers(3)), {KEYS[0]: 20, KEYS[4]: 10})
    assert [(t.key, t.current, t.target, t.gap) for t in result.items] == [
        (KEYS[0], 15, 20, 5),
        (KEYS[4], 15, 10, -5),
    ]
    assert result.items[0].name == QS.dimensions[0].name
    assert result.question_set_version == QS.version


def test_items_follow_book_order_not_input_order() -> None:
    result = readiness_targets(score_readiness(all_answers(3)), {KEYS[9]: 20, KEYS[2]: 20})
    assert [t.key for t in result.items] == [KEYS[2], KEYS[9]]


def test_gap_is_none_when_current_is_missing() -> None:
    answers = all_answers(3)
    del answers[QS.question_ids(KEYS[0])[0]]
    result = readiness_targets(score_readiness(answers), {KEYS[0]: 20, KEYS[1]: 20})
    assert [(t.current, t.gap) for t in result.items] == [(None, None), (15, 5)]


def test_no_targets_gives_no_items() -> None:
    assert readiness_targets(score_readiness(all_answers(3)), {}).items == ()


@pytest.mark.parametrize(("target", "ok"), [(4, False), (5, True), (25, True), (26, False)])
def test_readiness_target_range_is_5_to_25(target: int, ok: bool) -> None:
    result = score_readiness(all_answers(3))
    if ok:
        assert readiness_targets(result, {KEYS[0]: target}).items[0].target == target
    else:
        with pytest.raises(ScoringError, match="5 to 25"):
            readiness_targets(result, {KEYS[0]: target})


@pytest.mark.parametrize(("target", "ok"), [(0, False), (1, True), (10, True), (11, False)])
def test_iq_target_range_is_1_to_10(target: int, ok: bool) -> None:
    result = score_iq(iq_scores([5] * 12))
    if ok:
        assert iq_targets(result, {KEYS[0]: target}).items[0].gap == target - 5
    else:
        with pytest.raises(ScoringError, match="1 to 10"):
            iq_targets(result, {KEYS[0]: target})


@pytest.mark.parametrize("bad", [7.0, True, "7", Decimal(7), None])
def test_non_integer_targets_are_rejected(bad: Any) -> None:
    with pytest.raises(ScoringError, match="whole number"):
        iq_targets(score_iq(iq_scores([5] * 12)), {KEYS[0]: bad})
    with pytest.raises(ScoringError, match="whole number"):
        readiness_targets(score_readiness(all_answers(3)), {KEYS[0]: bad})


def test_unknown_dimension_is_rejected() -> None:
    with pytest.raises(ScoringError, match="Unknown dimension key"):
        iq_targets(score_iq(iq_scores([5] * 12)), {"risk": 5})


def test_targets_must_be_a_mapping() -> None:
    with pytest.raises(ScoringError, match="mapping"):
        iq_targets(score_iq(iq_scores([5] * 12)), [5])  # type: ignore[arg-type]


def test_iq_gap_none_when_unscored() -> None:
    result = iq_targets(score_iq({KEYS[1]: 4}), {KEYS[0]: 8, KEYS[1]: 8})
    assert [(t.current, t.gap) for t in result.items] == [(None, None), (4, 4)]


def test_other_question_set_version_is_rejected() -> None:
    other = dataclasses.replace(QS, version=QS.version + 1)
    with pytest.raises(ScoringError, match="question_set_version"):
        readiness_targets(score_readiness(all_answers(3)), {}, other)
    with pytest.raises(ScoringError, match="question_set_version"):
        iq_targets(score_iq(iq_scores([5] * 12)), {}, other)
