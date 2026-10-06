"""Fixed Decimal context (PROVISIONAL Q18): results never depend on the caller's settings."""

import decimal
from collections.abc import Iterator
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext

import pytest

from app.scoring import _rounding
from app.scoring._rounding import engine_math
from app.scoring.categories import iq_categories, readiness_categories
from app.scoring.errors import ScoringError
from app.scoring.iq import iq_maximum, score_iq
from app.scoring.readiness import score_readiness
from app.scoring.vfm import vfm
from tests.scoring.support import KEYS, answers_for_total, iq_scores, iq_scores_for_sum


def _everything() -> list[object]:
    weights = dict(zip(KEYS, [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3], strict=True))
    scores = iq_scores([7, 8, 6, 9, 5, 3, 4, 1, 1, 1, 1, 2])
    return [
        [score_iq(iq_scores_for_sum(total)).iq for total in range(12, 121)],
        score_iq(scores, weights=weights),
        score_iq(
            iq_scores([2, 1] + [1] * 10),
            weights={k: 1 if i == 0 else 199 if i == 1 else 0 for i, k in enumerate(KEYS)},
        ).iq,
        iq_categories(score_iq(scores)),
        readiness_categories(score_readiness(answers_for_total(187))),
        vfm(5_000_000, 2, Decimal("69.2")),
        vfm(30_000_000, 2, 84),
        vfm(5, 2, 10),
        vfm(10**40, 2, 10),
        iq_maximum(),
    ]


@pytest.fixture
def hostile_context() -> Iterator[None]:
    with localcontext() as ctx:
        ctx.prec = 3
        ctx.rounding = ROUND_DOWN
        ctx.traps[decimal.Inexact] = True
        ctx.traps[decimal.Rounded] = True
        yield


def test_rounding_is_half_up() -> None:
    assert _rounding.ROUNDING == ROUND_HALF_UP
    with engine_math() as ctx:
        assert ctx.rounding == ROUND_HALF_UP


def test_hostile_caller_context_gives_identical_results(hostile_context: None) -> None:
    with localcontext() as normal:
        normal.prec = 28
        normal.rounding = decimal.ROUND_HALF_EVEN
        normal.traps[decimal.Inexact] = False
        normal.traps[decimal.Rounded] = False
        expected = _everything()
    assert _everything() == expected
    assert str(score_iq(iq_scores_for_sum(83)).iq) == "69.2"
    assert str(vfm(5_000_000, 2, Decimal("69.2"))) == "722.54"


def test_caller_context_is_untouched_after_engine_math() -> None:
    with localcontext() as ctx:
        ctx.prec = 7
        ctx.rounding = ROUND_DOWN
        with engine_math() as inner:
            assert inner.prec == 50
            assert Decimal(2) / 3 == Decimal("0." + "6" * 49 + "7")
        assert decimal.getcontext().prec == 7
        assert decimal.getcontext().rounding == ROUND_DOWN


def test_engine_context_flags_do_not_accumulate() -> None:
    with engine_math():
        _ = Decimal(1) / 3
    assert not any(_rounding._ENGINE_CONTEXT.flags.values())


def test_engine_context_is_private() -> None:
    assert not hasattr(_rounding, "ENGINE_CONTEXT")


@pytest.mark.parametrize(
    "operation",
    [
        pytest.param(lambda: Decimal(1) / 0, id="division by zero"),
        pytest.param(lambda: Decimal(0) / 0, id="0 / 0"),
        pytest.param(lambda: Decimal("1E999999") * 10, id="overflow"),
        pytest.param(lambda: Decimal("1E-999999") / Decimal("1E999"), id="underflow"),
        pytest.param(lambda: Decimal(10**60).quantize(Decimal("0.01")), id="quantize too big"),
        pytest.param(lambda: Decimal("NaN") < 1, id="NaN compare"),
    ],
)
def test_decimal_errors_become_scoring_errors(operation: object) -> None:
    with pytest.raises(ScoringError, match="Arithmetic error"), engine_math():
        operation()  # type: ignore[operator]
