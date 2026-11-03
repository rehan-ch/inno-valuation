"""Dimension importance: the organisation's client weights (spec 3.4 and 7)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import RequestModel


class WeightOut(BaseModel):
    key: str
    name: str
    order: int
    category: str
    weight: str  # decimal string, e.g. "1" or "2.5"


class WeightLimitsOut(BaseModel):
    minimum: int
    maximum: int
    max_decimal_places: int


class WeightsOut(BaseModel):
    question_set_version: int
    weights: list[WeightOut]
    # Not every dimension counts the same, so tied priorities are ordered by importance.
    custom: bool
    set_at: datetime | None
    set_by_name: str | None
    can_change: bool
    limits: WeightLimitsOut


class WeightsChangeOut(BaseModel):
    id: uuid.UUID
    set_at: datetime
    set_by_name: str | None
    custom: bool
    weights: dict[str, str]


class WeightsIn(RequestModel):
    """Every dimension's weight. Numbers or decimal strings; the engine checks the limits."""

    weights: Annotated[dict[str, Decimal], Field(max_length=20)]
