"""Innovation Readiness, organisation level (spec section 2).

Answers in, numbers out. Readiness never mixes with IQ (spec 4). No per-dimension status
labels are produced: they are undecided (spec 2.5, open-questions Q4).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.scoring.errors import ScoringError, describe
from app.scoring.question_set import QUESTION_SET, QuestionSet, ReadinessBand


@dataclass(frozen=True, slots=True)
class DimensionReadiness:
    """One dimension's readiness score: the sum of its answers, or None if any is missing."""

    key: str
    name: str
    order: int
    category: str
    score: int | None
    answered: int


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Readiness for one organisation (spec 2.2 to 2.4).

    ``total`` and ``band`` are None unless every question is answered.
    """

    question_set_version: int
    dimensions: tuple[DimensionReadiness, ...]
    total: int | None
    band: ReadinessBand | None
    missing_question_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        """True when every question has an answer."""
        return not self.missing_question_ids


def _valid_answer(question_id: str, value: object, question_set: QuestionSet) -> int:
    scale = question_set.readiness_scale
    if not isinstance(value, int) or isinstance(value, bool):
        raise ScoringError(
            f"Answer to {question_id} must be a whole number {scale.min} to {scale.max}, "
            f"got {describe(value)}"
        )
    if not scale.min <= value <= scale.max:
        raise ScoringError(
            f"Answer to {question_id} must be {scale.min} to {scale.max}, got {describe(value)}"
        )
    return value


def validate_answers(
    answers: Mapping[str, object], question_set: QuestionSet = QUESTION_SET
) -> dict[str, int]:
    """Validate readiness answers and return the answered ones (spec 2.1).

    Keys are question ids from the question set. Values are integers on the readiness
    scale (1 to 5); ``None`` means unanswered. Bools, floats and strings are rejected.
    Raises ScoringError on unknown ids or invalid values.
    """
    if not isinstance(answers, Mapping):
        raise ScoringError(
            f"Answers must be a mapping of question id to answer, got {describe(answers)}"
        )
    valid: dict[str, int] = {}
    for question_id, value in answers.items():
        if not isinstance(question_id, str):
            raise ScoringError(f"Question id must be text, got {describe(question_id)}")
        question_set.dimension_of_question(question_id)
        if value is None:
            continue
        valid[question_id] = _valid_answer(question_id, value, question_set)
    return valid


def readiness_band(total: int, question_set: QuestionSet = QUESTION_SET) -> ReadinessBand:
    """The band for a complete readiness total, inclusive ranges (spec 2.4).

    Totals outside the possible range (60 to 300, derived from the question set) raise
    ScoringError.
    """
    if not isinstance(total, int) or isinstance(total, bool):
        raise ScoringError(f"Readiness total must be an integer, got {describe(total)}")
    if not question_set.total_min <= total <= question_set.total_max:
        raise ScoringError(
            f"Readiness total must be {question_set.total_min} to {question_set.total_max}, "
            f"got {describe(total)}"
        )
    for band in question_set.readiness_bands:
        if band.min <= total <= band.max:
            return band
    raise ScoringError(
        f"No readiness band covers {describe(total)}"
    )  # unreachable after validation


def score_readiness(
    answers: Mapping[str, object], question_set: QuestionSet = QUESTION_SET
) -> ReadinessResult:
    """Score readiness answers (spec 2.2 dimension sum, 2.3 total, 2.4 band).

    A missing answer never counts as 0: its dimension score, the total and the band are
    None and the result is not complete.
    """
    valid = validate_answers(answers, question_set)
    dimensions: list[DimensionReadiness] = []
    missing: list[str] = []
    for dimension in question_set.dimensions:
        ids = question_set.question_ids(dimension.key)
        present = [valid[q] for q in ids if q in valid]
        missing.extend(q for q in ids if q not in valid)
        dimensions.append(
            DimensionReadiness(
                key=dimension.key,
                name=dimension.name,
                order=dimension.order,
                category=dimension.category,
                score=sum(present) if len(present) == len(ids) else None,
                answered=len(present),
            )
        )
    total: int | None = None
    band: ReadinessBand | None = None
    if not missing:
        total = sum(d.score for d in dimensions if d.score is not None)
        band = readiness_band(total, question_set)
    return ReadinessResult(
        question_set_version=question_set.version,
        dimensions=tuple(dimensions),
        total=total,
        band=band,
        missing_question_ids=tuple(missing),
    )
