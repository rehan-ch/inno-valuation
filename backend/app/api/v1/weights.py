"""Dimension importance of the active organisation (spec 3.4 and 7; Amy Q2).

Weights never change a score or the IQ; they only order tied priorities (PROVISIONAL Q23).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import OrgContext, Permission
from app.models import DimensionWeights
from app.schemas.weights import (
    WeightLimitsOut,
    WeightOut,
    WeightsChangeOut,
    WeightsIn,
    WeightsOut,
)
from app.scoring.question_set import QUESTION_SET
from app.scoring.weights import WEIGHT_LIMITS
from app.services import ideas, weights

router = APIRouter(prefix="/weights", tags=["weights"])


def _names(db: Session, rows: list[DimensionWeights]) -> dict[uuid.UUID, str]:
    return ideas.user_names(db, {r.set_by_user_id for r in rows if r.set_by_user_id is not None})


def _weights_out(db: Session, ctx: OrgContext) -> WeightsOut:
    row = weights.latest(db, ctx.organisation_id)
    current = weights.weights_of(row)
    names = _names(db, [row]) if row is not None else {}
    set_at: datetime | None = row.created_at if row is not None else None
    return WeightsOut(
        question_set_version=QUESTION_SET.version,
        weights=[
            WeightOut(
                key=d.key,
                name=d.name,
                order=d.order,
                category=d.category,
                weight=str(current[d.key]),
            )
            for d in QUESTION_SET.dimensions
        ],
        custom=weights.is_custom(current),
        set_at=set_at,
        set_by_name=(
            names.get(row.set_by_user_id)
            if row is not None and row.set_by_user_id is not None
            else None
        ),
        can_change=ctx.can(Permission.MANAGE_WEIGHTS),
        limits=WeightLimitsOut(
            minimum=WEIGHT_LIMITS.minimum,
            maximum=WEIGHT_LIMITS.maximum,
            max_decimal_places=WEIGHT_LIMITS.max_decimal_places,
        ),
    )


@router.get("", response_model=WeightsOut, status_code=status.HTTP_200_OK)
def get_weights(
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ORGANISATION)),
    db: Session = Depends(get_db),
) -> WeightsOut:
    return _weights_out(db, ctx)


@router.get("/history", response_model=list[WeightsChangeOut], status_code=status.HTTP_200_OK)
def get_history(
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ORGANISATION)),
    db: Session = Depends(get_db),
) -> list[WeightsChangeOut]:
    rows = weights.history(db, ctx.organisation_id)
    names = _names(db, rows)
    return [
        WeightsChangeOut(
            id=row.id,
            set_at=row.created_at,
            set_by_name=names.get(row.set_by_user_id) if row.set_by_user_id else None,
            custom=weights.is_custom(row.weights),
            # In book order: JSONB keeps its own key order.
            weights={
                key: str(row.weights[key])
                for key in QUESTION_SET.dimension_keys
                if key in row.weights
            },
        )
        for row in rows
    ]


@router.put("", response_model=WeightsOut, status_code=status.HTTP_200_OK)
def set_weights(
    body: WeightsIn,
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_WEIGHTS)),
    db: Session = Depends(get_db),
) -> WeightsOut:
    weights.set_weights(db, ctx, body.weights)
    return _weights_out(db, ctx)


@router.post("/reset", response_model=WeightsOut, status_code=status.HTTP_200_OK)
def reset_weights(
    ctx: OrgContext = Depends(require_permission(Permission.MANAGE_WEIGHTS)),
    db: Session = Depends(get_db),
) -> WeightsOut:
    weights.reset_weights(db, ctx)
    return _weights_out(db, ctx)
