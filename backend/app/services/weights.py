"""Dimension importance: the organisation's client weights (spec 3.4 and 7; Amy Q2).

Weights never change a score or the IQ. They only decide the order of priorities whose
scores tie (PROVISIONAL, open-questions Q23), and only for ideas until Amy says otherwise.
Every change is a new ``dimension_weights`` row, so the history is the table itself; the
newest row is current, and no row means every dimension counts equally.
"""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.models import DimensionWeights
from app.scoring.errors import ScoringError
from app.scoring.question_set import QUESTION_SET, QuestionSet
from app.scoring.weights import validate_weights
from app.services.audit import AuditAction, record
from app.services.organisations import lock_organisation

EQUAL_WEIGHT: Final = Decimal(1)
HISTORY_LIMIT: Final = 50

Weights = Mapping[str, Decimal]


def equal_weights(question_set: QuestionSet = QUESTION_SET) -> Weights:
    """Every dimension counts the same: the default, and what "reset" writes."""
    return validate_weights(dict.fromkeys(question_set.dimension_keys, EQUAL_WEIGHT))


def snapshot(weights: Weights) -> dict[str, str]:
    """Weights as decimal strings in book order, for JSONB columns."""
    return {key: str(value) for key, value in weights.items()}


def from_snapshot(stored: Mapping[str, Any], question_set: QuestionSet) -> Weights | None:
    """The weights a row or snapshot holds, or None when they do not fit ``question_set``
    (another version, a hand-edited row): callers then fall back to equal weights."""
    try:
        return validate_weights(
            {str(key): Decimal(str(value)) for key, value in stored.items()},
            question_set=question_set,
        )
    except (ScoringError, ArithmeticError, TypeError):
        return None


def is_custom(weights: Mapping[str, Any] | None) -> bool:
    """Whether the weights make any difference: not every value the same."""
    if not weights:
        return False
    return len({str(Decimal(str(v))) for v in weights.values()}) > 1


def latest(db: Session, organisation_id: uuid.UUID) -> DimensionWeights | None:
    return db.scalars(
        select(DimensionWeights)
        .where(DimensionWeights.organisation_id == organisation_id)
        .order_by(DimensionWeights.created_at.desc(), DimensionWeights.id.desc())
        .limit(1)
    ).first()


def weights_of(row: DimensionWeights | None, question_set: QuestionSet = QUESTION_SET) -> Weights:
    """The weights a stored row means for ``question_set``: equal weights when there is no
    row or it was set on another question set version."""
    if row is None or row.question_set_version != question_set.version:
        return equal_weights(question_set)
    return from_snapshot(row.weights, question_set) or equal_weights(question_set)


def current_weights(
    db: Session, organisation_id: uuid.UUID, question_set: QuestionSet = QUESTION_SET
) -> Weights:
    """The organisation's weights for ``question_set``: the newest row, or equal weights."""
    return weights_of(latest(db, organisation_id), question_set)


def history(db: Session, organisation_id: uuid.UUID) -> list[DimensionWeights]:
    """Every change, newest first, up to ``HISTORY_LIMIT``."""
    return list(
        db.scalars(
            select(DimensionWeights)
            .where(DimensionWeights.organisation_id == organisation_id)
            .order_by(DimensionWeights.created_at.desc(), DimensionWeights.id.desc())
            .limit(HISTORY_LIMIT)
        )
    )


def set_weights(
    db: Session,
    ctx: OrgContext,
    weights: Mapping[str, object],
    question_set: QuestionSet = QUESTION_SET,
) -> Weights:
    """Replace the organisation's weights. Validated by the engine (422 ``invalid_weights``:
    every dimension, 0 to 1000, at most 6 decimals, not all zero; PROVISIONAL Q22). An
    unchanged set writes nothing. The audit event names the changed dimensions, never the
    values. Commits."""
    try:
        valid = validate_weights(weights, question_set=question_set)
    except ScoringError as error:
        raise AppError("invalid_weights", str(error), 422) from error
    lock_organisation(db, ctx.organisation)
    before = current_weights(db, ctx.organisation_id, question_set)
    changed = [key for key in question_set.dimension_keys if before[key] != valid[key]]
    if not changed:
        db.rollback()  # releases the lock; nothing to write
        return before
    db.add(
        DimensionWeights(
            organisation_id=ctx.organisation_id,
            question_set_version=question_set.version,
            weights=snapshot(valid),
            set_by_user_id=ctx.user.id,
            # Set here, not by the database: inside one transaction every row would get the
            # same time, and the newest row must be unambiguous.
            created_at=datetime.now(UTC),
        )
    )
    record(
        db,
        AuditAction.WEIGHTS_CHANGED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="organisation",
        target_id=ctx.organisation_id,
        details={"changed": changed, "custom": is_custom(valid)},
    )
    db.commit()
    return valid


def reset_weights(
    db: Session, ctx: OrgContext, question_set: QuestionSet = QUESTION_SET
) -> Weights:
    """Back to every dimension counting equally. Commits."""
    return set_weights(db, ctx, equal_weights(question_set), question_set)
