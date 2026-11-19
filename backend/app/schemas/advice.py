"""AI advice on one result, as the screens read it (Phase 6).

Four parts, each with its own status. The text is the AI's and is marked as such on the
screen; the only numbers here are a version and the engine's priority rank. Usage figures
are filled in for platform admins only.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import AdviceSubject
from app.schemas.common import RequestModel

# off: switched off on the server. none: never asked. pending: on its way (poll).
# ready: the newest run answered. failed: the newest run failed; an older answer, if there
# is one, is still returned.
PartStatus = Literal["off", "none", "pending", "ready", "failed"]
PartName = Literal["interpretation", "gap_actions", "recommendations", "consultation"]


class UsageOut(BaseModel):
    """What the shown answer cost. Platform admins only."""

    model: str | None
    input_tokens: int
    output_tokens: int
    # US dollars at list prices, to four decimals, as text: the screen shows it as sent.
    cost_usd: str


class PartOut(BaseModel):
    status: PartStatus
    # True when the text is the development stand-in's sample, not real advice.
    sample: bool
    # True when the same request would be worded differently today (the targets, the
    # company details, the prompt or the model changed): asking again refreshes it.
    outdated: bool
    generated_at: datetime | None
    usage: UsageOut | None


class DimensionMeaningOut(BaseModel):
    key: str
    name: str
    meaning: str
    strengths: list[str]
    gaps: list[str]


class InterpretationOut(PartOut):
    version: int | None
    summary: list[str]
    dimensions: list[DimensionMeaningOut]


class DimensionActionsOut(BaseModel):
    key: str
    name: str
    actions: list[str]


class GapActionsOut(PartOut):
    dimensions: list[DimensionActionsOut]


class RecommendationOut(BaseModel):
    key: str
    name: str
    # The engine's rank among the priorities (spec 7); 1 is the most urgent.
    rank: int
    # Amy's next steps for the dimension, verbatim from the question set (spec 8).
    fixed_text: str
    # The AI's tailored advice, kept apart from the fixed text.
    initiatives: list[str]
    kpis: list[str]
    timeline: str
    resources: list[str]


class RecommendationsOut(PartOut):
    version: int | None
    items: list[RecommendationOut]


class ConsultationReasonOut(BaseModel):
    key: str
    name: str
    reason: str


class ConsultationOut(PartOut):
    # The AI's judgement (Amy Q11): no fixed threshold.
    suggest: bool
    message: list[str]
    reasons: list[ConsultationReasonOut]


class AdviceOut(BaseModel):
    subject: AdviceSubject
    assessment_id: uuid.UUID
    question_set_version: int
    # Whether the caller may ask for advice or ask again.
    can_request: bool
    interpretation: InterpretationOut
    gap_actions: GapActionsOut
    recommendations: RecommendationsOut
    consultation: ConsultationOut


class AdviceRequestIn(RequestModel):
    # The parts to ask for; every part when left out.
    parts: list[PartName] | None = None
    # False asks only for parts that have no answer yet; true asks again.
    regenerate: bool = False
