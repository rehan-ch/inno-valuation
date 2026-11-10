"""Change over time between two results of the same kind (spec section 9)."""

from decimal import Decimal
from typing import Any

import pytest

from app.scoring.errors import ScoringError
from app.scoring.trend import (
    Direction,
    decimal_change,
    dimension_changes,
    require_comparable,
    whole_change,
)
from tests.scoring.support import KEYS, QS


def _scores(value: int, **changes: int) -> dict[str, int]:
    scores = dict.fromkeys(KEYS, value)
    scores.update(changes)
    return scores


@pytest.mark.parametrize(
    ("previous", "current", "change", "direction"),
    [(190, 205, 15, Direction.UP), (205, 190, -15, Direction.DOWN), (190, 190, 0, Direction.SAME)],
)
def test_change_is_current_minus_previous(
    previous: int, current: int, change: int, direction: Direction
) -> None:
    found = whole_change(previous, current)
    assert (found.previous, found.current) == (previous, current)
    assert found.change == change
    assert found.direction is direction


def test_decimal_change_is_exact_and_never_rounded_again() -> None:
    found = decimal_change(Decimal("69.2"), Decimal("70.0"))
    assert found.change == Decimal("0.8")
    assert found.direction is Direction.UP
    assert decimal_change(Decimal("714.29"), Decimal("694.44")).change == Decimal("-19.85")
    assert decimal_change(Decimal("70.0"), Decimal("70.0")).direction is Direction.SAME


@pytest.mark.parametrize("bad", [1.5, "3", True, None])
def test_whole_change_refuses_anything_but_whole_numbers(bad: Any) -> None:
    with pytest.raises(ScoringError, match="whole number"):
        whole_change(bad, 3)
    with pytest.raises(ScoringError, match="whole number"):
        whole_change(3, bad)


@pytest.mark.parametrize("bad", [70, 70.0, "70.0", None, Decimal("NaN"), Decimal("Infinity")])
def test_decimal_change_refuses_anything_but_finite_decimals(bad: Any) -> None:
    with pytest.raises(ScoringError, match="finite Decimal"):
        decimal_change(bad, Decimal("70.0"))
    with pytest.raises(ScoringError, match="finite Decimal"):
        decimal_change(Decimal("70.0"), bad)


def test_dimension_changes_follow_book_order() -> None:
    first, last = KEYS[0], KEYS[-1]
    changes = dimension_changes(
        _scores(15),
        _scores(15, **{first: 20, last: 12}),
        previous_version=QS.version,
        current_version=QS.version,
    )
    assert [c.key for c in changes] == list(KEYS)
    assert [c.order for c in changes] == [d.order for d in QS.dimensions]
    assert changes[0].name == QS.dimensions[0].name
    assert (changes[0].change.change, changes[0].change.direction) == (5, Direction.UP)
    assert (changes[-1].change.change, changes[-1].change.direction) == (-3, Direction.DOWN)
    assert {c.change.direction for c in changes[1:-1]} == {Direction.SAME}


def test_results_on_different_question_set_versions_are_never_compared() -> None:
    with pytest.raises(ScoringError, match="cannot be compared"):
        dimension_changes(
            _scores(15), _scores(16), previous_version=QS.version - 1, current_version=QS.version
        )
    with pytest.raises(ScoringError, match="cannot be compared"):
        dimension_changes(
            _scores(15),
            _scores(16),
            previous_version=QS.version + 1,
            current_version=QS.version + 1,
        )
    with pytest.raises(ScoringError, match="cannot be compared"):
        require_comparable(1, 2)
    require_comparable(2, 2)


def test_both_results_must_hold_every_dimension() -> None:
    partial = _scores(15)
    del partial[KEYS[3]]
    for previous, current in ((partial, _scores(15)), (_scores(15), partial)):
        with pytest.raises(ScoringError, match="every dimension"):
            dimension_changes(
                previous, current, previous_version=QS.version, current_version=QS.version
            )
    with pytest.raises(ScoringError, match="every dimension"):
        dimension_changes(
            {**_scores(15), "extra": 1},
            _scores(15),
            previous_version=QS.version,
            current_version=QS.version,
        )
