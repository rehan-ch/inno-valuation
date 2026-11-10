"""Idea and IQ assessment request and response models.

Money travels as decimal strings in major units (``"50000.00"``) with its ISO 4217 code;
the server stores minor units. IQ, category scores, confidence and Value for Money are
decimal strings too, so no float rounding reaches the client.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, StrictInt, StringConstraints, model_validator

from app.models.enums import IdeaStage, IdeaStatus, IqAssessmentStatus
from app.models.ideas import NOTE_MAX_LENGTH
from app.schemas.common import NoControlCharacters, RequestModel
from app.schemas.organisation import CurrencyCode


def _blank_to_none(value: str | None) -> str | None:
    return value or None


IdeaTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200), NoControlCharacters
]
IdeaText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
OptionalText = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None,
    AfterValidator(_blank_to_none),
]
# Major units. The decimal places a currency allows are checked by the service.
Money = Annotated[Decimal, Field(ge=0, max_digits=19, decimal_places=4)]

ProposalStatus = Literal["pending", "ready", "failed"]

# Fields that may be left out but never cleared.
_REQUIRED_WHEN_SENT = ("title", "summary", "stage", "currency")


class IdeaUpdateIn(RequestModel):
    """Partial update: only the fields sent are changed. Send null to clear an optional one."""

    title: IdeaTitle | None = None
    summary: IdeaText | None = None
    problem: OptionalText = None
    target_market: OptionalText = None
    uniqueness: OptionalText = None
    team: OptionalText = None
    risks: OptionalText = None
    stage: IdeaStage | None = None
    investment: Money | None = None
    expected_value: Money | None = None
    currency: CurrencyCode | None = None

    @model_validator(mode="after")
    def _required_fields_not_cleared(self) -> Self:
        for field in _REQUIRED_WHEN_SENT:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be empty")
        return self

    def changes(self) -> dict[str, object]:
        """The fields the client sent."""
        return {field: getattr(self, field) for field in sorted(self.model_fields_set)}


class IdeaCreateIn(IdeaUpdateIn):
    """A new idea: a title and summary are required; the currency defaults to the
    organisation's."""

    title: IdeaTitle
    summary: IdeaText
    stage: IdeaStage = IdeaStage.IDEA

    def values(self) -> dict[str, object]:
        return {field: value for field, value in self if value is not None}


class AssessmentBriefOut(BaseModel):
    """One assessment in a list: where it stands and, once confirmed, its headline numbers."""

    id: uuid.UUID
    status: IqAssessmentStatus
    proposal_status: ProposalStatus
    # The proposal came from the development stand-in, not a real model.
    sample: bool
    iq: str | None
    vfm_per_point: str | None
    currency: str | None
    requested_at: datetime
    confirmed_at: datetime | None


class IdeaSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    stage: IdeaStage
    status: IdeaStatus
    archived: bool
    currency: str
    investment: str | None
    expected_value: str | None
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
    latest_assessment: AssessmentBriefOut | None


class IdeaOut(IdeaSummaryOut):
    summary: str
    problem: str | None
    target_market: str | None
    uniqueness: str | None
    team: str | None
    risks: str | None
    # The caller may edit, score, review and confirm this idea (its creator, or a manager).
    can_change: bool
    can_archive: bool
    assessments: list[AssessmentBriefOut]


class LevelOut(BaseModel):
    key: str
    name: str
    min: int
    max: int
    text: str


class IqScaleOut(BaseModel):
    min: int
    max: int


class DimensionReviewOut(BaseModel):
    """One dimension of an assessment: the AI's proposal beside the owner's final score."""

    key: str
    name: str
    order: int
    category: str
    description: str
    proposed_score: int | None
    proposed_rationale: list[str] | None
    proposed_confidence: str | None
    # The owner's choice so far; null means the proposal stands.
    final_score: int | None
    # The engine's level (spec 3.1) of the score in force: the owner's choice, else the
    # proposal; fixed at confirmation. Null until a proposal exists.
    level: LevelOut | None
    note: str | None
    changed: bool


class IqCategoryOut(BaseModel):
    key: str
    name: str
    score: str | None
    maximum: str


class IqPriorityOut(BaseModel):
    rank: int
    key: str
    name: str
    score: int
    level_name: str
    next_steps: str


class VfmOut(BaseModel):
    """Value for Money (spec 5.1): the investment the assessment was confirmed with and the
    cost per innovation point, or why there is none."""

    investment: str | None
    currency: str
    per_point: str | None
    not_calculable_reason: str | None


class IqAssessmentOut(BaseModel):
    id: uuid.UUID
    idea_id: uuid.UUID
    idea_title: str
    status: IqAssessmentStatus
    proposal_status: ProposalStatus
    sample: bool
    question_set_version: int
    scale: IqScaleOut
    levels: list[LevelOut]
    dimensions: list[DimensionReviewOut]
    # The AI's open questions about the idea, if any.
    missing_information: list[str]
    iq: str | None
    iq_maximum: str
    categories: list[IqCategoryOut]
    priorities: list[IqPriorityOut]
    # The organisation had custom dimension importance when this was confirmed, so tied
    # priorities are ordered by it (never the scores).
    custom_weights: bool
    vfm: VfmOut | None
    can_review: bool
    requested_at: datetime
    requested_by_name: str | None
    confirmed_at: datetime | None
    confirmed_by_name: str | None


ScoreMap = Annotated[dict[str, StrictInt | None], Field(max_length=20)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=NOTE_MAX_LENGTH)]
NoteMap = Annotated[dict[str, Note | None], Field(max_length=20)]


class ReviewIn(RequestModel):
    """The owner's review: changed scores (null puts the proposal back) and notes."""

    scores: ScoreMap = Field(default_factory=dict)
    notes: NoteMap = Field(default_factory=dict)
