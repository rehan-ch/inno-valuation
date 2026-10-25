"""Touchpoint 1 output: what one readiness question means, in plain words.

Helps only: it carries no number of any kind, and names the question's dimension.
"""

from pydantic import Field

from app.ai.schemas.common import AiOutput, DimensionKey, Sentence


class ExplainQuestionOutput(AiOutput):
    dimension_key: DimensionKey
    explanation: list[Sentence] = Field(min_length=2, max_length=4)
    example: Sentence
