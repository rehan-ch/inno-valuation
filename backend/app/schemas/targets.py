"""Targets per dimension (spec 6; PROVISIONAL Q8) and the gap to the current score."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StrictInt

from app.models.enums import TargetScale
from app.schemas.common import RequestModel


class TargetOut(BaseModel):
    key: str
    name: str
    order: int
    category: str
    # Null when no target is set for this dimension.
    target: int | None


class TargetScaleOut(BaseModel):
    """One scale's targets. Readiness and IQ targets are separate and never mixed."""

    scale: TargetScale
    # The range a target may take: a dimension score on this scale.
    minimum: int
    maximum: int
    targets: list[TargetOut]
    set_at: datetime | None
    set_by_name: str | None


class TargetsOut(BaseModel):
    question_set_version: int
    readiness: TargetScaleOut
    iq: TargetScaleOut
    can_change: bool


class TargetsChangeOut(BaseModel):
    id: uuid.UUID
    scale: TargetScale
    set_at: datetime
    set_by_name: str | None
    # {dimension key: target} as it stood after this change.
    targets: dict[str, int]
    # The dimensions whose target this change set, moved or removed, in book order.
    changed: list[str]


class TargetsIn(RequestModel):
    """Every target of one scale: a dimension left out (or null) has no target."""

    targets: Annotated[dict[str, StrictInt | None], Field(max_length=20)]
