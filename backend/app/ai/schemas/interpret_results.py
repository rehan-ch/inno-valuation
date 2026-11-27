"""Touchpoint 4 output: what one result means, overall and per dimension.

Suggests only. The output holds words, never a number: no score, total, band, rank or
value for money (spec 2 to 7 belong to the engine), and a check refuses any digit in the
text. Every item names its dimension.
"""

from typing import Final, Self

from pydantic import Field, model_validator

from app.ai.schemas.common import AiOutput, DimensionKey, Words

# The exact dimension keys belong to the result's question set version:
# ``touchpoints.interpret_results.spec_for`` puts them in the schema and checks the output.
MAX_DIMENSIONS: Final = 50
MAX_POINTS: Final = 3


class DimensionMeaning(AiOutput):
    dimension_key: DimensionKey
    # What this dimension's score says about the company or the idea, in one sentence.
    meaning: Words
    # What looks strong here, and what is weak or missing. Either may be empty.
    strengths: list[Words] = Field(max_length=MAX_POINTS)
    gaps: list[Words] = Field(max_length=MAX_POINTS)


class InterpretResultsOutput(AiOutput):
    # What the result as a whole means, in 2 to 4 short sentences.
    summary: list[Words] = Field(min_length=2, max_length=4)
    dimensions: list[DimensionMeaning] = Field(min_length=1, max_length=MAX_DIMENSIONS)

    @model_validator(mode="after")
    def _each_dimension_at_most_once(self) -> Self:
        keys = [d.dimension_key for d in self.dimensions]
        if len(set(keys)) != len(keys):
            raise ValueError("a dimension may be explained only once")
        return self
