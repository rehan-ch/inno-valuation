"""Builders for engine tests. Everything is derived from the loaded question set."""

import copy
from collections.abc import Callable, Sequence
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from app.scoring.question_set import DEFAULT_QUESTION_SET_PATH, QUESTION_SET, QuestionSet

QS = QUESTION_SET
KEYS = QS.dimension_keys


def all_answers(value: object, qs: QuestionSet = QS) -> dict[str, object]:
    return dict.fromkeys(qs.all_question_ids(), value)


def answers_for_dimension_scores(scores: Sequence[int], qs: QuestionSet = QS) -> dict[str, int]:
    """Answers (1 to 5) whose dimension sums equal ``scores`` (5 to 25), in book order."""
    answers: dict[str, int] = {}
    for dimension, score in zip(qs.dimensions, scores, strict=True):
        extra = score - qs.dimension_min
        for question in dimension.questions:
            step = min(qs.readiness_scale.max - qs.readiness_scale.min, extra)
            answers[question.id] = qs.readiness_scale.min + step
            extra -= step
        assert extra == 0, f"score {score} not reachable"
    return answers


def answers_for_total(total: int, qs: QuestionSet = QS) -> dict[str, int]:
    """Answers whose total is ``total`` (60 to 300)."""
    extra = total - qs.total_min
    scores = []
    for _ in qs.dimensions:
        step = min(qs.dimension_max - qs.dimension_min, extra)
        scores.append(qs.dimension_min + step)
        extra -= step
    assert extra == 0
    return answers_for_dimension_scores(scores, qs)


def iq_scores(values: Sequence[int]) -> dict[str, int]:
    return dict(zip(KEYS, values, strict=True))


def iq_scores_for_sum(total: int) -> dict[str, int]:
    """Scores (1 to 10) adding up to ``total`` (12 to 120)."""
    extra = total - len(KEYS)
    values = []
    for _ in KEYS:
        step = min(9, extra)
        values.append(1 + step)
        extra -= step
    assert extra == 0
    return iq_scores(values)


_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


@cache
def _raw_once() -> dict[str, Any]:
    data = yaml.load(DEFAULT_QUESTION_SET_PATH.read_text(encoding="utf-8"), Loader=_LOADER)  # noqa: S506
    assert isinstance(data, dict)
    return data


def raw_question_set() -> dict[str, Any]:
    """A fresh, mutable copy of the real dimensions.yml data."""
    return copy.deepcopy(_raw_once())


def write_variant(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], object], name: str = "qs.yml"
) -> Path:
    data = raw_question_set()
    mutate(data)
    path = tmp_path / name
    path.write_text(yaml.dump(data, Dumper=_DUMPER, sort_keys=False), encoding="utf-8")
    return path
