"""Touchpoint 5 output: 3 to 5 concrete actions per dimension, to move it from its current
score towards its target.

Suggests only. Which dimensions are asked about comes from the engine (the priorities,
spec 7, and the dimensions with a target, spec 6); the output adds no score of its own.
"""

from typing import Final, Self

from pydantic import Field, model_validator

from app.ai.schemas.common import AiOutput, DimensionKey, Words

MAX_DIMENSIONS: Final = 50
MIN_ACTIONS: Final = 3
MAX_ACTIONS: Final = 5


class DimensionActions(AiOutput):
    dimension_key: DimensionKey
    actions: list[Words] = Field(min_length=MIN_ACTIONS, max_length=MAX_ACTIONS)


class BridgeGapsOutput(AiOutput):
    dimensions: list[DimensionActions] = Field(min_length=1, max_length=MAX_DIMENSIONS)

    @model_validator(mode="after")
    def _each_dimension_at_most_once(self) -> Self:
        keys = [d.dimension_key for d in self.dimensions]
        if len(set(keys)) != len(keys):
            raise ValueError("a dimension may be listed only once")
        return self
