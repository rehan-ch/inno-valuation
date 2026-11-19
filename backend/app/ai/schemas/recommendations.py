"""Touchpoint 6 output: one recommendation per priority dimension.

``fixed_text`` is Amy's next-step text for the dimension (spec 8). It is passed in and
must come back unchanged; the touchpoint's check compares it character for character. The
rest is the AI's tailored advice: initiatives, KPIs, a timeline and resources. Which
dimensions are priorities, and in which order, is the engine's (spec 7): the output has no
field for it.
"""

from typing import Annotated, Final, Self

from pydantic import Field, StringConstraints, model_validator

from app.ai.schemas.common import AiOutput, DimensionKey, Words

MAX_DIMENSIONS: Final = 50
FIXED_TEXT_MAX: Final = 2000


class DimensionRecommendation(AiOutput):
    dimension_key: DimensionKey
    # The book's next steps, returned exactly as given. Not trimmed, not checked for style.
    fixed_text: Annotated[str, StringConstraints(min_length=1, max_length=FIXED_TEXT_MAX)]
    # Pieces of work the company could start.
    initiatives: list[Words] = Field(min_length=2, max_length=4)
    # What to measure to see whether it works. Names of measures, not invented figures.
    kpis: list[Words] = Field(min_length=2, max_length=4)
    # A realistic order and pace, in one sentence. Lengths of time in words, like all advice.
    timeline: Words
    # People, skills or tools it needs.
    resources: list[Words] = Field(min_length=1, max_length=4)


class RecommendationsOutput(AiOutput):
    recommendations: list[DimensionRecommendation] = Field(min_length=1, max_length=MAX_DIMENSIONS)

    @model_validator(mode="after")
    def _each_dimension_at_most_once(self) -> Self:
        keys = [r.dimension_key for r in self.recommendations]
        if len(set(keys)) != len(keys):
            raise ValueError("a dimension may be recommended on only once")
        return self
