"""Readiness assessment request and response models.

Answers travel as ``{question_id: 1..5}``. A ``null`` value in a request clears that
answer. Means are decimal strings with 2 places, so no float rounding reaches the client.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictInt

from app.models.enums import ReadinessStatus
from app.schemas.common import RequestModel

# The engine checks the scale and the ids; this only keeps payloads sane. StrictInt, so
# "3" and true are refused instead of quietly becoming 3 and 1.
AnswerMap = Annotated[dict[str, StrictInt | None], Field(max_length=100)]
NoteMap = Annotated[dict[str, str | None], Field(max_length=100)]

MyStatus = Literal["not_started", "in_progress", "submitted"]


class QuestionOut(BaseModel):
    id: str
    text: str


class DimensionOut(BaseModel):
    key: str
    name: str
    order: int
    category: str
    description: str
    questions: list[QuestionOut]


class CategoryOut(BaseModel):
    key: str
    name: str
    order: int


class ScaleOut(BaseModel):
    min: int
    max: int
    # {"1": "Strongly Disagree", "5": "Strongly Agree"}: only the ends are named in the book.
    labels: dict[str, str]


class QuestionSetOut(BaseModel):
    version: int
    scale: ScaleOut
    categories: list[CategoryOut]
    dimensions: list[DimensionOut]


class AssessmentSummaryOut(BaseModel):
    id: uuid.UUID
    status: ReadinessStatus
    question_set_version: int
    created_at: datetime
    started_at: datetime | None
    finalised_at: datetime | None
    created_by_name: str | None
    submitted_count: int
    # The caller's own progress; null when the caller does not answer (investor, consultant).
    my_status: MyStatus | None
    total: int | None
    band_name: str | None


class ParticipantOut(BaseModel):
    user_id: uuid.UUID
    name: str
    answered: int
    submitted_at: datetime | None


class AssessmentOut(AssessmentSummaryOut):
    my_answers: dict[str, int] | None
    my_submitted_at: datetime | None
    question_count: int
    can_answer: bool
    can_manage: bool
    # Everyone's progress, for the facilitator only; null for everyone else.
    participants: list[ParticipantOut] | None


class AnswersIn(RequestModel):
    answers: AnswerMap


class PersonAnswerOut(BaseModel):
    user_id: uuid.UUID
    name: str
    answer: int


class QuestionConsensusOut(BaseModel):
    question_id: str
    dimension_key: str
    answers: list[PersonAnswerOut]
    mean: str | None
    spread: int | None
    wide_spread: bool
    agreed: int | None
    note: str | None


class ConsensusOut(BaseModel):
    assessment_id: uuid.UUID
    status: ReadinessStatus
    participants: list[str]
    agreed_count: int
    question_count: int
    questions: list[QuestionConsensusOut]


class ConsensusIn(RequestModel):
    answers: AnswerMap = Field(default_factory=dict)
    notes: NoteMap = Field(default_factory=dict)


class BandOut(BaseModel):
    key: str
    name: str
    text: str


class DimensionScoreOut(BaseModel):
    key: str
    name: str
    order: int
    category: str
    score: int
    maximum: int


class CategoryScoreOut(BaseModel):
    key: str
    name: str
    score: int
    maximum: int


class PriorityOut(BaseModel):
    rank: int
    key: str
    name: str
    score: int
    maximum: int
    next_steps: str


class ResultOut(BaseModel):
    assessment_id: uuid.UUID
    question_set_version: int
    total: int
    total_maximum: int
    band: BandOut
    dimensions: list[DimensionScoreOut]
    categories: list[CategoryScoreOut]
    priorities: list[PriorityOut]
    strengths: list[DimensionScoreOut]
    submitted_count: int
    finalised_at: datetime
