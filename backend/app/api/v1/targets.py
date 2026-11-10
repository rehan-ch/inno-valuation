"""Target scores per dimension of the active organisation (spec 6; PROVISIONAL Q8).

A target changes no score. Gaps are shown with each result (dashboard, drill-down, history).
"""

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import OrgContext, Permission
from app.models.enums import TargetScale
from app.schemas.targets import (
    TargetOut,
    TargetScaleOut,
    TargetsChangeOut,
    TargetsIn,
    TargetsOut,
)
from app.scoring.question_set import QUESTION_SET
from app.services import ideas, targets

router = APIRouter(prefix="/targets", tags=["targets"])


def _scale_out(db: Session, ctx: OrgContext, scale: TargetScale) -> TargetScaleOut:
    row = targets.latest(db, ctx.organisation_id, scale)
    current = targets.targets_of(row)
    minimum, maximum = targets.target_range(scale)
    names = (
        ideas.user_names(db, {row.set_by_user_id})
        if row is not None and row.set_by_user_id is not None
        else {}
    )
    return TargetScaleOut(
        scale=scale,
        minimum=minimum,
        maximum=maximum,
        targets=[
            TargetOut(
                key=d.key,
                name=d.name,
                order=d.order,
                category=d.category,
                target=current.get(d.key),
            )
            for d in QUESTION_SET.dimensions
        ],
        set_at=row.created_at if row is not None else None,
        set_by_name=(
            names.get(row.set_by_user_id)
            if row is not None and row.set_by_user_id is not None
            else None
        ),
    )


def _in_book_order(stored: Mapping[str, Any]) -> dict[str, int]:
    """A stored row's targets in book order (JSONB keeps its own key order)."""
    order = {key: i for i, key in enumerate(QUESTION_SET.dimension_keys)}
    return {
        str(key): int(stored[key])
        for key in sorted(stored, key=lambda k: order.get(str(k), len(order)))
    }


def _targets_out(db: Session, ctx: OrgContext) -> TargetsOut:
    return TargetsOut(
        question_set_version=QUESTION_SET.version,
        readiness=_scale_out(db, ctx, TargetScale.READINESS),
        iq=_scale_out(db, ctx, TargetScale.IQ),
        can_change=ctx.can(Permission.MANAGE_TARGETS),
    )


@router.get("", response_model=TargetsOut, status_code=status.HTTP_200_OK)
def get_targets(
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> TargetsOut:
    """The organisation's targets per dimension on both scales, kept apart."""
    return _targets_out(db, ctx)


@router.get("/history", response_model=list[TargetsChangeOut], status_code=status.HTTP_200_OK)
def get_history(
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> list[TargetsChangeOut]:
    """Every change of the targets, newest first: earlier targets are kept."""
    rows = targets.history(db, ctx.organisation_id)
    names = ideas.user_names(db, {r.set_by_user_id for r in rows if r.set_by_user_id is not None})
    # Each change is compared with the one before it on the same scale.
    older: dict[TargetScale, dict[str, int]] = {}
    if len(rows) == targets.HISTORY_LIMIT:
        # The list is cut off: the oldest shown change of each scale has an earlier one.
        for row in reversed(rows):
            if row.scale not in older:
                before_row = targets.predecessor(db, row)
                older[row.scale] = _in_book_order(before_row.targets) if before_row else {}
    changes: list[TargetsChangeOut] = []
    for row in reversed(rows):
        after = _in_book_order(row.targets)
        before = older.get(row.scale, {})
        changes.append(
            TargetsChangeOut(
                id=row.id,
                scale=row.scale,
                set_at=row.created_at,
                set_by_name=names.get(row.set_by_user_id) if row.set_by_user_id else None,
                targets=after,
                changed=[
                    d.key for d in QUESTION_SET.dimensions if before.get(d.key) != after.get(d.key)
                ],
            )
        )
        older[row.scale] = after
    return list(reversed(changes))


@router.put("/{scale}", response_model=TargetsOut, status_code=status.HTTP_200_OK)
def set_targets(
    scale: TargetScale,
    body: TargetsIn,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_TARGETS)),
    db: Session = Depends(get_db),
) -> TargetsOut:
    """Replace one scale's targets. A dimension left out, or sent as null, has no target."""
    targets.set_targets(db, ctx, scale, body.targets)
    return _targets_out(db, ctx)
