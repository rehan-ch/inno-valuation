"""What the advice touchpoints (4, 5, 6 and 8) are told about one result.

``ResultFacts`` is one final readiness result or one confirmed IQ assessment, as stored:
the engine's numbers, the question set's names and texts, and the details that may go to
the AI provider. Nothing here computes a score, a rank or a gap; ``app.services.advice``
fills it from the stored result and the engine's gaps.

A run's subject is ``<question set version>:<assessment id>``. Its ``params`` hold the
dimension keys the prompt asked about (``{"keys": [...]}``), so the answer is checked
against exactly what was asked, whatever has changed since.
"""

import json
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel

from app.ai.runner import OutputRejectedError
from app.models import AiRun
from app.models.enums import AdviceSubject
from app.scoring.question_set import (
    Dimension,
    IqLevel,
    QuestionSet,
    ReadinessBand,
    question_set_for,
)

SAMPLE_NOTE: Final = "This is sample text, because the AI service is not connected yet."


@dataclass(frozen=True, slots=True)
class DimensionFact:
    """One dimension of the result. Every number is the engine's."""

    dimension: Dimension
    score: int
    maximum: int
    # The IQ level of the score (spec 3.1); None on a readiness result (Q4).
    level: IqLevel | None
    # The rank among the priorities (spec 7), 1 the most urgent; None when not a priority.
    rank: int | None
    # The organisation's target and the gap to it (target minus score, spec 6), when set.
    target: int | None
    gap: int | None


@dataclass(frozen=True, slots=True)
class ResultFacts:
    subject: AdviceSubject
    subject_id: uuid.UUID
    question_set: QuestionSet
    # The readiness total (out of 300) or the IQ (out of 100), as text, with its maximum.
    total: str
    total_maximum: str
    band: ReadinessBand | None
    # Book order.
    dimensions: tuple[DimensionFact, ...]
    # Keys of the dimensions shown as strengths (the engine's choice), highest first.
    strength_keys: tuple[str, ...]
    # "Label: value" lines that may go to the AI provider (PROVISIONAL Q10); "" when none.
    company: str
    idea: str

    @property
    def readiness(self) -> bool:
        return self.subject is AdviceSubject.READINESS_RESULT

    def fact(self, key: str) -> DimensionFact:
        return next(f for f in self.dimensions if f.dimension.key == key)

    @property
    def priorities(self) -> tuple[DimensionFact, ...]:
        """The priority dimensions, most urgent first."""
        ranked = [f for f in self.dimensions if f.rank is not None]
        return tuple(sorted(ranked, key=lambda f: f.rank or 0))

    @property
    def strengths(self) -> tuple[DimensionFact, ...]:
        return tuple(self.fact(key) for key in self.strength_keys)

    @property
    def focus(self) -> tuple[DimensionFact, ...]:
        """The dimensions to close gaps on: the priorities, then every other dimension
        whose target is above its score, in book order."""
        targeted = [
            f for f in self.dimensions if f.rank is None and f.gap is not None and f.gap > 0
        ]
        return (*self.priorities, *targeted)


def subject_id(version: int, assessment_id: uuid.UUID) -> str:
    return f"{version}:{assessment_id}"


def parse_subject(value: str) -> tuple[int, uuid.UUID]:
    version, _, assessment_id = value.partition(":")
    return int(version), uuid.UUID(assessment_id)


def keys_param(facts: tuple[DimensionFact, ...]) -> dict[str, Any]:
    return {"keys": [f.dimension.key for f in facts]}


def asked(run: AiRun) -> tuple[QuestionSet, list[str]]:
    """The question set of the run's subject and the dimension keys its prompt asked about."""
    version, _ = parse_subject(run.subject_id)
    question_set = question_set_for(version)
    keys = [str(key) for key in (run.params or {}).get("keys", [])]
    known = set(question_set.dimension_keys)
    if not keys or any(key not in known for key in keys):
        raise OutputRejectedError("The run does not say which dimensions it asked about.")
    return question_set, keys


def require_exactly(found: list[str], keys: list[str], what: str) -> None:
    if sorted(found) != sorted(keys):
        raise OutputRejectedError(
            f"{what} must cover exactly the dimensions asked about, once each: {', '.join(keys)}."
        )


# Advice is about one result on one scale (spec 4: the two are never added, blended or set
# against each other). Advice on a readiness result may not bring in the Innovation
# Quotient, and advice on an idea may not bring in Innovation Readiness.
_OTHER_SCALE: Final = {
    AdviceSubject.READINESS_RESULT: re.compile(r"innovation\s+quotient|\bIQ\b", re.IGNORECASE),
    AdviceSubject.IQ_ASSESSMENT: re.compile(r"innovation\s+readiness", re.IGNORECASE),
}
# Copied or fixed values, not the AI's own words.
_NOT_WORDS: Final = frozenset({"dimension_key", "fixed_text"})


def _words(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for name, inner in value.items():
            if name not in _NOT_WORDS:
                yield from _words(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _words(inner)


def require_one_scale(run: AiRun, output: BaseModel) -> None:
    """Refuse advice whose words bring in the other score."""
    pattern = _OTHER_SCALE[AdviceSubject(run.subject_type)]
    if any(pattern.search(text) for text in _words(output.model_dump())):
        raise OutputRejectedError(
            "The advice is about this result only. Do not mention the other score."
        )


def dumps(value: dict[str, Any]) -> str:
    return json.dumps(value)
