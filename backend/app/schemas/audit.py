"""The organisation's activity log (Phase 5, P5.10). Read-only: there is no request model
that changes an event."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    at: datetime
    # The stored action code ("iq.confirmed") and what it means in plain words.
    action: str
    action_label: str
    actor_id: uuid.UUID | None
    # Null when the person's account no longer exists.
    actor_name: str | None
    # What it was done to, when that has a name: a person, an idea, an invited address.
    subject: str | None
    # The recorded details in plain words. Never a score, an answer or any idea text.
    detail: str | None
    # The method (question set) version and the AI model involved, when recorded.
    question_set_version: int | None
    ai_model: str | None


class AuditPageOut(BaseModel):
    # Newest first.
    events: list[AuditEventOut]
    # Pass as ``before`` to get the next page; null on the last page.
    next_before: str | None


class AuditActionOut(BaseModel):
    action: str
    label: str


class AuditActorOut(BaseModel):
    id: uuid.UUID
    name: str


class AuditFiltersOut(BaseModel):
    """What the log can be filtered by: the actions and the people that appear in it."""

    actions: list[AuditActionOut]
    actors: list[AuditActorOut]
