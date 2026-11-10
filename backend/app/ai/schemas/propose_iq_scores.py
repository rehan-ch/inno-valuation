"""Touchpoint 3 output: a proposed 1 to 10 score per dimension, with its reasons.

Proposes only (Amy Q1): the idea owner confirms or changes every score. The output
carries no IQ, total, level, band or value for money; those come from the scoring engine
(spec 3.1, 3.2, 3.6, 5, 7), and a schema test proves the fields are not here.
"""

from typing import Annotated, Final, Self

from pydantic import Field, StrictInt, model_validator

from app.ai.schemas.common import AiOutput, DimensionKey, Sentence
from app.scoring.question_set import QUESTION_SET

SCORE_MIN: Final = QUESTION_SET.iq_scale.min
SCORE_MAX: Final = QUESTION_SET.iq_scale.max
# The exact dimension keys and count belong to the assessment's question set version:
# ``touchpoints.propose_iq_scores.spec_for`` puts them in the schema and checks the output.
MAX_DIMENSIONS: Final = 50
MAX_OPEN_QUESTIONS: Final = 5


class ProposedScore(AiOutput):
    dimension_key: DimensionKey
    # A whole number on the IQ scale (spec 3.1). The level is not asked for: the engine
    # derives it from the score.
    score: Annotated[StrictInt, Field(ge=SCORE_MIN, le=SCORE_MAX)]
    # 2 to 4 short sentences, quoting the idea, treating its claims as claims.
    rationale: list[Sentence] = Field(min_length=2, max_length=4)
    # How sure the model is, 0 to 1. Shown beside the score; never used in any arithmetic.
    confidence: Annotated[float, Field(ge=0, le=1)]


class ProposeIqScoresOutput(AiOutput):
    scores: list[ProposedScore] = Field(min_length=1, max_length=MAX_DIMENSIONS)
    # Short questions whose answers would make the scores more certain; empty if none.
    missing_information: list[Sentence] = Field(default_factory=list, max_length=MAX_OPEN_QUESTIONS)

    @model_validator(mode="after")
    def _each_dimension_at_most_once(self) -> Self:
        keys = [s.dimension_key for s in self.scores]
        if len(set(keys)) != len(keys):
            raise ValueError("a dimension may be scored only once")
        return self
