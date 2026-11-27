"""Touchpoint 8 output: whether to suggest booking a consultation, and why.

There is no fixed threshold (Amy Q11, spec 10): the AI judges whether the gap between
where the company is and where it wants to be is significant. When it suggests one, a
short message says so and every reason names the dimension behind it. When it does not,
there is no message and no reason.
"""

from typing import Final, Self

from pydantic import Field, model_validator

from app.ai.schemas.common import AiOutput, DimensionKey, Words

MAX_REASONS: Final = 5


class NudgeReason(AiOutput):
    dimension_key: DimensionKey
    reason: Words


class ConsultationNudgeOutput(AiOutput):
    suggest: bool
    # One or two short sentences recommending a consultation; empty when ``suggest`` is false.
    message: list[Words] = Field(max_length=2)
    reasons: list[NudgeReason] = Field(max_length=MAX_REASONS)

    @model_validator(mode="after")
    def _message_and_reasons_only_with_a_suggestion(self) -> Self:
        if self.suggest and not (self.message and self.reasons):
            raise ValueError("a suggestion needs a message and at least one reason")
        if not self.suggest and (self.message or self.reasons):
            raise ValueError("without a suggestion there is no message and no reason")
        keys = [r.dimension_key for r in self.reasons]
        if len(set(keys)) != len(keys):
            raise ValueError("a dimension may be named only once")
        return self
