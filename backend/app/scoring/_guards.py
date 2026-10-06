"""Checks shared by functions that take an earlier result plus a question set (spec 9)."""

from collections.abc import Sequence

from app.scoring.errors import ScoringError, describe
from app.scoring.question_set import QuestionSet


def require_same_version(
    result_version: int, dimension_keys: Sequence[str], question_set: QuestionSet
) -> None:
    """Reject a result built from a different question bank than ``question_set``.

    Spec 9: comparisons and derived views use the same ``question_set_version``.
    """
    if result_version != question_set.version:
        raise ScoringError(
            f"Result uses question_set_version {describe(result_version)}, "
            f"but question set version {question_set.version} was given"
        )
    if tuple(dimension_keys) != question_set.dimension_keys:
        raise ScoringError("Result dimensions do not match the question set in book order")


def require_complete(complete: bool, what: str) -> None:
    """Reject an incomplete result where every dimension score is needed."""
    if not complete:
        raise ScoringError(f"{what} needs a complete result (every dimension scored)")
