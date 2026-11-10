"""The 12-segment compass of one result on one scale (Phase 5, P5.03).

Readiness and IQ each have their own compass and never share one (spec 4). The client
draws what is here and computes nothing.
"""

from typing import Literal

from pydantic import BaseModel

Scale = Literal["readiness", "iq"]
Direction = Literal["up", "down", "same"]


class SegmentLevelOut(BaseModel):
    """The book's level of one IQ dimension score (spec 3.1). ``order`` is its place among
    the levels, lowest first, so the compass can colour segments without knowing a level."""

    key: str
    name: str
    order: int


class CompassSegmentOut(BaseModel):
    """One dimension of the compass, in book order."""

    key: str
    name: str
    order: int
    category: str
    score: int
    maximum: int
    # IQ only. Readiness has no per-dimension labels (open-questions Q4), so it is null.
    level: SegmentLevelOut | None
    # Its place in the priorities list (1 is the most urgent); null when it is not on it.
    priority_rank: int | None
    # The organisation's target for this dimension on this scale, and target minus score.
    target: int | None
    gap: int | None


class CompassCategoryOut(BaseModel):
    key: str
    name: str
    order: int
    # Readiness: the sum of its dimension scores. IQ: the category IQ, 1 decimal.
    score: str
    maximum: str
    dimension_keys: list[str]


class CompassLevelOut(BaseModel):
    key: str
    name: str
    order: int
    min: int
    max: int
    text: str


class CompassOut(BaseModel):
    """Everything the 12-segment compass draws, for one result on one scale."""

    scale: Scale
    question_set_version: int
    # The range of one dimension score on this scale (5 to 25, or 1 to 10).
    minimum: int
    maximum: int
    segments: list[CompassSegmentOut]
    categories: list[CompassCategoryOut]
    # The legend: the book's IQ levels, lowest first. Empty for readiness.
    levels: list[CompassLevelOut]
