"""Category aggregates for readiness and IQ (spec 2.6 and 3.6, formula pending Q9).

Readiness and IQ categories are computed separately; no function takes both.
"""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from app.scoring._guards import require_same_version
from app.scoring._rounding import IQ_DECIMAL_PLACES, rational_to_decimal
from app.scoring.iq import IqResult, iq_maximum
from app.scoring.question_set import QUESTION_SET, QuestionSet
from app.scoring.readiness import ReadinessResult


@dataclass(frozen=True, slots=True)
class ReadinessCategoryScore:
    """Sum of a category's readiness dimension scores, shown with its maximum."""

    key: str
    name: str
    order: int
    dimension_keys: tuple[str, ...]
    score: int | None
    maximum: int


@dataclass(frozen=True, slots=True)
class ReadinessCategories:
    """Readiness per category, in category order (spec 2.6)."""

    question_set_version: int
    categories: tuple[ReadinessCategoryScore, ...]


@dataclass(frozen=True, slots=True)
class IqCategoryScore:
    """Category IQ: plain mean of its dimension scores x 10, out of 100."""

    key: str
    name: str
    order: int
    dimension_keys: tuple[str, ...]
    score: Decimal | None
    maximum: Decimal


@dataclass(frozen=True, slots=True)
class IqCategories:
    """IQ per category, in category order (spec 3.6)."""

    question_set_version: int
    categories: tuple[IqCategoryScore, ...]


# PROVISIONAL: see open-questions Q9
def readiness_categories(
    result: ReadinessResult, question_set: QuestionSet = QUESTION_SET
) -> ReadinessCategories:
    """Readiness category score = sum of its dimension scores (spec 2.6, PROPOSED).

    The maximum is derived from the question set (spec 2.6 lists 125, 50 and 125). A
    category with any unscored dimension has score None.
    """
    require_same_version(
        result.question_set_version, [d.key for d in result.dimensions], question_set
    )
    by_key = {d.key: d.score for d in result.dimensions}
    items = []
    for category in question_set.categories:
        keys = tuple(d.key for d in question_set.dimensions_in_category(category.key))
        scores = [by_key[k] for k in keys]
        present = [s for s in scores if s is not None]
        items.append(
            ReadinessCategoryScore(
                key=category.key,
                name=category.name,
                order=category.order,
                dimension_keys=keys,
                score=sum(present) if len(present) == len(scores) else None,
                maximum=len(keys) * question_set.dimension_max,
            )
        )
    return ReadinessCategories(
        question_set_version=result.question_set_version, categories=tuple(items)
    )


# PROVISIONAL: see open-questions Q9
def iq_categories(result: IqResult, question_set: QuestionSet = QUESTION_SET) -> IqCategories:
    """Category IQ = mean of its dimension scores x 10, out of 100 (spec 3.6, PROPOSED).

    A category with any unscored dimension has score None.
    """
    require_same_version(
        result.question_set_version, [d.key for d in result.dimensions], question_set
    )
    by_key = {d.key: d.score for d in result.dimensions}
    top = question_set.iq_scale.max
    items = []
    for category in question_set.categories:
        keys = tuple(d.key for d in question_set.dimensions_in_category(category.key))
        scores = [by_key[k] for k in keys]
        present = [s for s in scores if s is not None]
        score: Decimal | None = None
        if len(present) == len(scores):
            # PROVISIONAL: see open-questions Q20 (custom weights do not apply inside a category)
            mean_times_ten = Fraction(sum(present) * 100, len(present) * top)
            # PROVISIONAL: see open-questions Q18 (category IQ shows 1 decimal)
            score = rational_to_decimal(mean_times_ten, IQ_DECIMAL_PLACES)
        items.append(
            IqCategoryScore(
                key=category.key,
                name=category.name,
                order=category.order,
                dimension_keys=keys,
                score=score,
                maximum=iq_maximum(question_set),
            )
        )
    return IqCategories(question_set_version=result.question_set_version, categories=tuple(items))
