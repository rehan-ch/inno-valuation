"""Read the organisation's activity log (Phase 5, P5.10).

The log is the ``audit_events`` table, written by ``app.services.audit.record`` in the same
transaction as the action itself. This module only reads: no function here, and no route,
changes or deletes an event. Only events that belong to the organisation are shown; a
person's own sign-ins (no organisation) are not.

Details are turned into plain words here. They never held secrets, answers, scores or idea
text in the first place; names (a person, an idea) are looked up at read time, for readers
who may already see them.
"""

import base64
import binascii
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import AuditEvent, ConsultantGrant, Idea, Invitation, IqAssessment, User
from app.scoring.question_set import QUESTION_SET
from app.services.audit import AuditAction

PAGE_SIZE: Final = 50
MAX_PAGE_SIZE: Final = 200
EXPORT_LIMIT: Final = 5000

ACTION_LABELS: Final[Mapping[str, str]] = {
    AuditAction.ORGANISATION_CREATED: "Organisation created",
    AuditAction.ORGANISATION_UPDATED: "Organisation profile changed",
    AuditAction.MEMBER_INVITED: "Team member invited",
    AuditAction.INVITATION_REVOKED: "Invitation cancelled",
    AuditAction.INVITATION_ACCEPTED: "Invitation accepted",
    AuditAction.MEMBER_ROLE_CHANGED: "Role changed",
    AuditAction.MEMBER_REMOVED: "Team member removed",
    AuditAction.CONSULTANT_ACCESS_GRANTED: "Consultant access given",
    AuditAction.CONSULTANT_ACCESS_CHANGED: "Consultant access end date changed",
    AuditAction.CONSULTANT_ACCESS_REVOKED: "Consultant access ended",
    AuditAction.CONSULTANT_ACCESS_ACCEPTED: "Consultant access accepted",
    AuditAction.READINESS_STARTED: "Readiness assessment started",
    AuditAction.READINESS_RESPONSE_SUBMITTED: "Readiness answers submitted",
    AuditAction.READINESS_CONSENSUS_STARTED: "Agreeing the readiness answers started",
    AuditAction.READINESS_FINALISED: "Readiness result made final",
    AuditAction.IDEA_CREATED: "Idea added",
    AuditAction.IDEA_UPDATED: "Idea changed",
    AuditAction.IDEA_ARCHIVED: "Idea archived",
    AuditAction.IDEA_RESTORED: "Idea restored",
    AuditAction.IQ_REQUESTED: "AI score proposal requested",
    AuditAction.IQ_CONFIRMED: "Idea scores confirmed",
    AuditAction.WEIGHTS_CHANGED: "Dimension importance changed",
    AuditAction.TARGETS_CHANGED: "Targets changed",
}


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


@dataclass(frozen=True, slots=True)
class Filters:
    action: str | None = None
    actor_id: uuid.UUID | None = None


def _cursor(event: AuditEvent) -> str:
    raw = f"{event.created_at.isoformat()}|{event.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _parse_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        at, _, event_id = raw.partition("|")
        return datetime.fromisoformat(at), uuid.UUID(event_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as error:
        raise AppError("invalid_cursor", "This page link is not valid.", 422) from error


def _query(organisation_id: uuid.UUID, filters: Filters) -> Any:
    stmt = select(AuditEvent).where(AuditEvent.organisation_id == organisation_id)
    if filters.action is not None:
        stmt = stmt.where(AuditEvent.action == filters.action)
    if filters.actor_id is not None:
        stmt = stmt.where(AuditEvent.actor_user_id == filters.actor_id)
    return stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())


def page(
    db: Session,
    organisation_id: uuid.UUID,
    filters: Filters,
    *,
    before: str | None = None,
    limit: int = PAGE_SIZE,
) -> tuple[list[AuditEvent], str | None]:
    """One page of the organisation's events, newest first, and the cursor of the next
    page (None on the last)."""
    stmt = _query(organisation_id, filters)
    if before is not None:
        at, event_id = _parse_cursor(before)
        stmt = stmt.where(
            or_(
                AuditEvent.created_at < at,
                and_(AuditEvent.created_at == at, AuditEvent.id < event_id),
            )
        )
    events = list(db.scalars(stmt.limit(limit + 1)))
    if len(events) > limit:
        events = events[:limit]
        return events, _cursor(events[-1])
    return events, None


def export(
    db: Session, organisation_id: uuid.UUID, filters: Filters
) -> tuple[list[AuditEvent], bool]:
    """Up to ``EXPORT_LIMIT`` events, newest first, for the CSV download, and whether older
    ones were left out."""
    events = list(db.scalars(_query(organisation_id, filters).limit(EXPORT_LIMIT + 1)))
    return events[:EXPORT_LIMIT], len(events) > EXPORT_LIMIT


def actions_in_use(db: Session, organisation_id: uuid.UUID) -> list[str]:
    """The action codes that appear in the organisation's log, by label."""
    found = db.scalars(
        select(AuditEvent.action).where(AuditEvent.organisation_id == organisation_id).distinct()
    )
    return sorted(found, key=action_label)


def actors(db: Session, organisation_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    """The people who appear in the organisation's log and still have an account."""
    rows = db.execute(
        select(User.id, User.name)
        .where(
            User.id.in_(
                select(AuditEvent.actor_user_id).where(
                    AuditEvent.organisation_id == organisation_id,
                    AuditEvent.actor_user_id.is_not(None),
                )
            )
        )
        .order_by(User.name, User.id)
    ).all()
    return [(row[0], row[1]) for row in rows]


# In plain words


@dataclass(frozen=True, slots=True)
class Described:
    event: AuditEvent
    actor_name: str | None
    subject: str | None
    detail: str | None
    question_set_version: int | None
    ai_model: str | None


def _ids(events: Sequence[AuditEvent], target_type: str) -> set[uuid.UUID]:
    return {e.target_id for e in events if e.target_type == target_type and e.target_id is not None}


def _dimension_names(keys: Any) -> list[str]:
    names = {d.key: d.name for d in QUESTION_SET.dimensions}
    if not isinstance(keys, list):
        return []
    return [names.get(str(key), str(key)) for key in keys]


def _words(value: Any) -> str:
    return str(value).replace("_", " ")


def _day(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value)).date().isoformat()
    except ValueError:
        return str(value)


def _detail(event: AuditEvent) -> str | None:  # noqa: PLR0911, PLR0912 (one case per action)
    details = event.details or {}
    action = event.action
    if action in (AuditAction.ORGANISATION_UPDATED, AuditAction.IDEA_UPDATED):
        fields = details.get("fields")
        if isinstance(fields, list) and fields:
            return "Changed: " + ", ".join(_words(f) for f in fields) + "."
    elif action == AuditAction.MEMBER_ROLE_CHANGED:
        if "from" in details and "to" in details:
            return f"From {_words(details['from'])} to {_words(details['to'])}."
    elif action in (
        AuditAction.MEMBER_INVITED,
        AuditAction.MEMBER_REMOVED,
        AuditAction.INVITATION_ACCEPTED,
    ):
        if "role" in details:
            return f"Role: {_words(details['role'])}."
    elif action == AuditAction.CONSULTANT_ACCESS_GRANTED:
        if "expires_at" in details:
            return f"Access until {_day(details['expires_at'])}."
    elif action == AuditAction.CONSULTANT_ACCESS_CHANGED:
        if "from" in details and "to" in details:
            return f"End date moved from {_day(details['from'])} to {_day(details['to'])}."
    elif action == AuditAction.CONSULTANT_ACCESS_REVOKED:
        if details.get("reason") == "became_member":
            return "Ended because the consultant became a team member."
    elif action == AuditAction.READINESS_CONSENSUS_STARTED:
        if "submitted" in details:
            count = details["submitted"]
            return f"{count} {'person' if count == 1 else 'people'} had submitted answers."
    elif action == AuditAction.IQ_REQUESTED:
        return "Scored again." if details.get("rerun") else "First scoring of this idea."
    elif action == AuditAction.IQ_CONFIRMED:
        changed = _dimension_names(details.get("changed"))
        if not changed:
            return "Every proposed score was kept."
        text = "Changed from the AI's proposal: " + ", ".join(changed) + "."
        noted = _dimension_names(details.get("with_note"))
        if noted:
            text += " A note is on record for: " + ", ".join(noted) + "."
        return text
    elif action == AuditAction.WEIGHTS_CHANGED:
        changed = _dimension_names(details.get("changed"))
        if changed:
            return "Importance changed for: " + ", ".join(changed) + "."
    elif action == AuditAction.TARGETS_CHANGED:
        scale = "Readiness" if details.get("scale") == "readiness" else "Idea (IQ)"
        changed = _dimension_names(details.get("changed"))
        if changed:
            return f"{scale} targets changed for: " + ", ".join(changed) + "."
    return None


def describe(
    db: Session, organisation_id: uuid.UUID, events: Sequence[AuditEvent]
) -> list[Described]:
    """Each event with its names looked up, in a fixed number of queries. Ideas,
    assessments, invitations and grants are looked up inside the organisation only, so an
    id in an event can never name another organisation's record."""
    user_ids = {e.actor_user_id for e in events if e.actor_user_id is not None} | _ids(
        events, "user"
    )
    users: dict[uuid.UUID, str] = (
        {
            row[0]: row[1]
            for row in db.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
        }
        if user_ids
        else {}
    )
    idea_ids = _ids(events, "idea")
    assessment_ids = _ids(events, "iq_assessment")
    assessment_ideas: dict[uuid.UUID, uuid.UUID] = (
        {
            row[0]: row[1]
            for row in db.execute(
                select(IqAssessment.id, IqAssessment.idea_id).where(
                    IqAssessment.id.in_(assessment_ids),
                    IqAssessment.organisation_id == organisation_id,
                )
            )
        }
        if assessment_ids
        else {}
    )
    all_idea_ids = idea_ids | set(assessment_ideas.values())
    ideas: dict[uuid.UUID, str] = (
        {
            row[0]: row[1]
            for row in db.execute(
                select(Idea.id, Idea.title).where(
                    Idea.id.in_(all_idea_ids), Idea.organisation_id == organisation_id
                )
            )
        }
        if all_idea_ids
        else {}
    )
    invitation_ids = _ids(events, "invitation")
    invitations: dict[uuid.UUID, str] = (
        {
            row[0]: row[1]
            for row in db.execute(
                select(Invitation.id, Invitation.email).where(
                    Invitation.id.in_(invitation_ids),
                    Invitation.organisation_id == organisation_id,
                )
            )
        }
        if invitation_ids
        else {}
    )
    grant_ids = _ids(events, "consultant_grant")
    grants: dict[uuid.UUID, str] = (
        {
            row[0]: row[1]
            for row in db.execute(
                select(ConsultantGrant.id, ConsultantGrant.consultant_email).where(
                    ConsultantGrant.id.in_(grant_ids),
                    ConsultantGrant.organisation_id == organisation_id,
                )
            )
        }
        if grant_ids
        else {}
    )

    described = []
    for event in events:
        subject: str | None = None
        if event.target_id is not None:
            if event.target_type == "user":
                subject = users.get(event.target_id)
            elif event.target_type == "idea":
                subject = ideas.get(event.target_id)
            elif event.target_type == "iq_assessment":
                idea_id = assessment_ideas.get(event.target_id)
                subject = ideas.get(idea_id) if idea_id is not None else None
            elif event.target_type == "invitation":
                subject = invitations.get(event.target_id)
            elif event.target_type == "consultant_grant":
                subject = grants.get(event.target_id)
        details = event.details or {}
        version = details.get("question_set_version")
        model = details.get("ai_model")
        described.append(
            Described(
                event=event,
                actor_name=users.get(event.actor_user_id) if event.actor_user_id else None,
                subject=subject,
                detail=_detail(event),
                question_set_version=version if isinstance(version, int) else None,
                ai_model=str(model) if model else None,
            )
        )
    return described
