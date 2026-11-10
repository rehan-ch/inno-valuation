"""The activity log of the active organisation (Phase 5, P5.10): who did what, when, and
which method version and AI model were involved. Read-only: this router has no route that
changes or deletes an event."""

import csv
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import OrgContext, Permission
from app.schemas.audit import (
    AuditActionOut,
    AuditActorOut,
    AuditEventOut,
    AuditFiltersOut,
    AuditPageOut,
)
from app.services import audit_log
from app.services.audit_log import Described, Filters

router = APIRouter(prefix="/audit", tags=["audit"])

_view = require_permission(Permission.VIEW_AUDIT)

Action = Annotated[str | None, Query(max_length=64)]
Cursor = Annotated[str | None, Query(max_length=200)]
Limit = Annotated[int, Query(ge=1, le=audit_log.MAX_PAGE_SIZE)]

# A cell that starts with one of these would run as a formula when the file is opened in a
# spreadsheet, so it is written as text.
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _event_out(item: Described) -> AuditEventOut:
    event = item.event
    return AuditEventOut(
        id=event.id,
        at=event.created_at,
        action=event.action,
        action_label=audit_log.action_label(event.action),
        actor_id=event.actor_user_id,
        actor_name=item.actor_name,
        subject=item.subject,
        detail=item.detail,
        question_set_version=item.question_set_version,
        ai_model=item.ai_model,
    )


@router.get("", response_model=AuditPageOut, status_code=status.HTTP_200_OK)
def list_events(
    *,
    action: Action = None,
    actor_id: uuid.UUID | None = None,
    before: Cursor = None,
    limit: Limit = audit_log.PAGE_SIZE,
    ctx: OrgContext = Depends(_view),
    db: Session = Depends(get_db),
) -> AuditPageOut:
    """The organisation's recorded actions, newest first, optionally only one action or one
    person. ``next_before`` is the cursor of the next page."""
    events, next_before = audit_log.page(
        db,
        ctx.organisation_id,
        Filters(action=action, actor_id=actor_id),
        before=before,
        limit=limit,
    )
    return AuditPageOut(
        events=[_event_out(item) for item in audit_log.describe(db, events)],
        next_before=next_before,
    )


@router.get("/filters", response_model=AuditFiltersOut, status_code=status.HTTP_200_OK)
def get_filters(ctx: OrgContext = Depends(_view), db: Session = Depends(get_db)) -> AuditFiltersOut:
    return AuditFiltersOut(
        actions=[
            AuditActionOut(action=action, label=audit_log.action_label(action))
            for action in audit_log.actions_in_use(db, ctx.organisation_id)
        ],
        actors=[
            AuditActorOut(id=user_id, name=name)
            for user_id, name in audit_log.actors(db, ctx.organisation_id)
        ],
    )


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(_FORMULA_STARTS) else text


@router.get("/export", status_code=status.HTTP_200_OK, response_class=Response)
def export_events(
    action: Action = None,
    actor_id: uuid.UUID | None = None,
    ctx: OrgContext = Depends(_view),
    db: Session = Depends(get_db),
) -> Response:
    """The same list as a CSV file (newest first, at most 5,000 rows), with the same
    filters. Times are UTC."""
    events = audit_log.export(db, ctx.organisation_id, Filters(action=action, actor_id=actor_id))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["Time (UTC)", "Person", "Action", "About", "Details", "Question set version", "AI model"]
    )
    for item in audit_log.describe(db, events):
        writer.writerow(
            [
                item.event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                _cell(item.actor_name or "Someone who has left"),
                _cell(audit_log.action_label(item.event.action)),
                _cell(item.subject),
                _cell(item.detail),
                item.question_set_version if item.question_set_version is not None else "",
                _cell(item.ai_model),
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="activity-log.csv"'},
    )
