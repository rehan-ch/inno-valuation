"""Dashboard, compass, drill-down and history response models (Phase 5).

Readiness and IQ never share a field: every model here belongs to one scale or holds the
two side by side (spec 4). Decimal figures (IQ, category IQ, Value for Money) are strings.
Nothing here is computed by the client: scores, levels, gaps and changes come from the
scoring engine.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.compass import CompassOut, Direction
from app.schemas.ideas import LevelOut, VfmOut
from app.schemas.readiness import BandOut, CategoryOut, ScaleOut


class PriorityItemOut(BaseModel):
    rank: int
    key: str
    name: str
    score: int
    maximum: int
    # IQ only: the level of the score.
    level_name: str | None
    # The book's fixed next-step text for the dimension, as written.
    next_steps: str


class ReadinessHeadlineOut(BaseModel):
    """The organisation's latest final readiness result."""

    assessment_id: uuid.UUID
    finalised_at: datetime
    question_set_version: int
    total: int
    total_maximum: int
    band: BandOut
    compass: CompassOut
    priorities: list[PriorityItemOut]


class IdeaChoiceOut(BaseModel):
    """An idea with a confirmed IQ assessment, for the idea picker."""

    idea_id: uuid.UUID
    title: str
    assessment_id: uuid.UUID
    iq: str
    confirmed_at: datetime


class IqHeadlineOut(BaseModel):
    """The selected idea's latest confirmed IQ assessment."""

    idea_id: uuid.UUID
    idea_title: str
    assessment_id: uuid.UUID
    confirmed_at: datetime
    question_set_version: int
    iq: str
    iq_maximum: str
    vfm: VfmOut | None
    # Tied priorities were ordered by the organisation's dimension importance.
    custom_weights: bool
    compass: CompassOut
    priorities: list[PriorityItemOut]


class DashboardOut(BaseModel):
    """The two headline scores side by side, never combined (spec 4)."""

    readiness: ReadinessHeadlineOut | None
    # Ideas that can be selected, most recently confirmed first.
    ideas: list[IdeaChoiceOut]
    iq: IqHeadlineOut | None


class DimensionRefOut(BaseModel):
    key: str
    name: str
    order: int


class QuestionAnswerOut(BaseModel):
    id: str
    text: str
    # The team's agreed answer (Amy Q5); null if it is not on record.
    answer: int | None


class TrendPointOut(BaseModel):
    """One earlier or current score of a dimension, with its change from the result before
    it on the same question set version (null when there is none to compare with)."""

    assessment_id: uuid.UUID
    at: datetime
    score: int
    maximum: int
    change: int | None
    direction: Direction | None


class DimensionReadinessOut(BaseModel):
    assessment_id: uuid.UUID
    finalised_at: datetime
    question_set_version: int
    score: int
    maximum: int
    priority_rank: int | None
    target: int | None
    gap: int | None
    answer_scale: ScaleOut
    questions: list[QuestionAnswerOut]
    # Newest first.
    history: list[TrendPointOut]


class DimensionIqOut(BaseModel):
    idea_id: uuid.UUID
    idea_title: str
    assessment_id: uuid.UUID
    confirmed_at: datetime
    question_set_version: int
    score: int
    maximum: int
    level: LevelOut
    # What the AI proposed, and whether the owner changed it (Amy Q1).
    proposed_score: int | None
    changed: bool
    rationale: list[str]
    note: str | None
    priority_rank: int | None
    target: int | None
    gap: int | None
    history: list[TrendPointOut]


class DimensionDetailOut(BaseModel):
    """One dimension: the book's text, and its score on each scale, kept apart."""

    key: str
    name: str
    order: int
    category: CategoryOut
    description: str
    sub_aspects: list[str]
    # The book's fixed next-step text, as written (spec 8).
    next_steps: str
    previous: DimensionRefOut | None
    next: DimensionRefOut | None
    readiness: DimensionReadinessOut | None
    ideas: list[IdeaChoiceOut]
    iq: DimensionIqOut | None


class HistoryDimensionOut(BaseModel):
    key: str
    name: str
    order: int
    score: int
    maximum: int
    change: int | None
    direction: Direction | None
    # Against the organisation's target as it stands today.
    target: int | None
    gap: int | None


class ReadinessHistoryEntryOut(BaseModel):
    assessment_id: uuid.UUID
    finalised_at: datetime
    question_set_version: int
    total: int
    total_maximum: int
    band_name: str
    # The earlier result this one is compared with: the one before it on the same question
    # set version (spec 9). Null for the first, and then every change is null.
    compared_with: uuid.UUID | None
    total_change: int | None
    total_direction: Direction | None
    dimensions: list[HistoryDimensionOut]


class ReadinessHistoryOut(BaseModel):
    # Newest first.
    entries: list[ReadinessHistoryEntryOut]


class IqHistoryEntryOut(BaseModel):
    assessment_id: uuid.UUID
    confirmed_at: datetime
    question_set_version: int
    iq: str
    iq_maximum: str
    compared_with: uuid.UUID | None
    iq_change: str | None
    iq_direction: Direction | None
    vfm: VfmOut | None
    # Compared only when both assessments have a Value for Money in the same currency.
    # A lower cost per innovation point is better.
    vfm_change: str | None
    vfm_direction: Direction | None
    dimensions: list[HistoryDimensionOut]


class IdeaHistoryOut(BaseModel):
    idea_id: uuid.UUID
    idea_title: str
    # Newest first.
    entries: list[IqHistoryEntryOut]
