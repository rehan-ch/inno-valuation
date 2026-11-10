"""Targets per dimension and the gap to a result (spec 6).

PROVISIONAL: see open-questions Q8. Until Amy decides where targets can be set, a target
sits on one dimension, on either scale: a readiness dimension score (5 to 25) or an idea's
dimension score (1 to 10). An IQ target is the organisation's ambition for that dimension
and is held against every idea. The two scales are stored and read separately (spec 4).

A target changes no score. The gap is ``target - current``, worked out by the engine
(``app.scoring.targets``), never here. Every change is a new ``dimension_targets`` row, so
the history is the table itself; the newest row of a scale is current.
"""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.models import DimensionTargets
from app.models.enums import TargetScale
from app.scoring import iq as iq_engine
from app.scoring import readiness as readiness_engine
from app.scoring import targets as targets_engine
from app.scoring.errors import ScoringError
from app.scoring.question_set import QUESTION_SET, QuestionSet
from app.scoring.targets import TargetGap
from app.services.audit import AuditAction, record
from app.services.organisations import lock_organisation

HISTORY_LIMIT: Final = 50

Targets = Mapping[str, int]


def _validated(
    scale: TargetScale, targets: Mapping[str, object], question_set: QuestionSet
) -> dict[str, int]:
    if scale is TargetScale.READINESS:
        return targets_engine.validate_readiness_targets(targets, question_set)
    return targets_engine.validate_iq_targets(targets, question_set)


def target_range(scale: TargetScale, question_set: QuestionSet = QUESTION_SET) -> tuple[int, int]:
    """The lowest and highest target on ``scale``: a dimension score's own range."""
    if scale is TargetScale.READINESS:
        return question_set.dimension_min, question_set.dimension_max
    return question_set.iq_scale.min, question_set.iq_scale.max


def latest(db: Session, organisation_id: uuid.UUID, scale: TargetScale) -> DimensionTargets | None:
    return db.scalars(
        select(DimensionTargets)
        .where(DimensionTargets.organisation_id == organisation_id, DimensionTargets.scale == scale)
        .order_by(DimensionTargets.created_at.desc(), DimensionTargets.id.desc())
        .limit(1)
    ).first()


def targets_of(row: DimensionTargets | None, question_set: QuestionSet = QUESTION_SET) -> Targets:
    """The targets a stored row means for ``question_set``, in book order: none when there
    is no row, it was set on another question set version, or it no longer validates."""
    if row is None or row.question_set_version != question_set.version:
        return {}
    try:
        valid = _validated(row.scale, dict(row.targets), question_set)
    except ScoringError:
        return {}
    return {key: valid[key] for key in question_set.dimension_keys if key in valid}


def current_targets(
    db: Session,
    organisation_id: uuid.UUID,
    scale: TargetScale,
    question_set: QuestionSet = QUESTION_SET,
) -> Targets:
    return targets_of(latest(db, organisation_id, scale), question_set)


def history(db: Session, organisation_id: uuid.UUID) -> list[DimensionTargets]:
    """Every change on both scales, newest first, up to ``HISTORY_LIMIT``."""
    return list(
        db.scalars(
            select(DimensionTargets)
            .where(DimensionTargets.organisation_id == organisation_id)
            .order_by(DimensionTargets.created_at.desc(), DimensionTargets.id.desc())
            .limit(HISTORY_LIMIT)
        )
    )


def changed_keys(before: Targets, after: Targets, question_set: QuestionSet) -> list[str]:
    """Dimensions whose target was set, moved or removed, in book order."""
    return [key for key in question_set.dimension_keys if before.get(key) != after.get(key)]


def set_targets(
    db: Session,
    ctx: OrgContext,
    scale: TargetScale,
    targets: Mapping[str, object],
    question_set: QuestionSet = QUESTION_SET,
) -> Targets:
    """Replace the organisation's targets on ``scale``; a dimension left out or null has no
    target. Validated by the engine (422 ``invalid_targets``: known dimensions, whole
    numbers in the scale's range). An unchanged set writes nothing. The audit event names
    the scale and the changed dimensions, never the values. Commits."""
    wanted = {key: value for key, value in targets.items() if value is not None}
    try:
        valid = _validated(scale, wanted, question_set)
    except ScoringError as error:
        raise AppError("invalid_targets", str(error), 422) from error
    ordered = {key: valid[key] for key in question_set.dimension_keys if key in valid}
    lock_organisation(db, ctx.organisation)
    before = current_targets(db, ctx.organisation_id, scale, question_set)
    changed = changed_keys(before, ordered, question_set)
    if not changed:
        db.rollback()  # releases the lock; nothing to write
        return before
    db.add(
        DimensionTargets(
            organisation_id=ctx.organisation_id,
            scale=scale,
            question_set_version=question_set.version,
            targets=ordered,
            set_by_user_id=ctx.user.id,
            # Set here, not by the database: inside one transaction every row would get the
            # same time, and the newest row must be unambiguous.
            created_at=datetime.now(UTC),
        )
    )
    record(
        db,
        AuditAction.TARGETS_CHANGED,
        actor=ctx.user,
        organisation_id=ctx.organisation_id,
        target_type="organisation",
        target_id=ctx.organisation_id,
        details={
            "scale": scale.value,
            "changed": changed,
            "question_set_version": question_set.version,
        },
    )
    db.commit()
    return ordered


# Gaps. PROVISIONAL: see open-questions Q8 (per dimension, both scales).


def readiness_gaps(
    targets: Targets,
    agreed_answers: Mapping[str, Any] | None,
    stored_scores: Mapping[str, Any],
    question_set: QuestionSet,
) -> dict[str, TargetGap]:
    """Target and gap per dimension for one final readiness result (spec 6), by key; only
    dimensions with a target. The engine scores the agreed answers again to work out the
    gaps; if that does not reproduce the stored result (or the agreed answers are gone),
    no gap is shown rather than a wrong one."""
    if not targets or agreed_answers is None:
        return {}
    try:
        scored = readiness_engine.score_readiness(dict(agreed_answers), question_set)
        if {d.key: d.score for d in scored.dimensions} != {
            key: int(value) for key, value in stored_scores.items()
        }:
            return {}
        return {
            gap.key: gap
            for gap in targets_engine.readiness_targets(scored, targets, question_set).items
        }
    except (ScoringError, TypeError, ValueError):
        return {}


def iq_gaps(
    targets: Targets, final_scores: Mapping[str, int], question_set: QuestionSet
) -> dict[str, TargetGap]:
    """Target and gap per dimension for one confirmed IQ assessment (spec 6), by key; only
    dimensions with a target."""
    if not targets:
        return {}
    try:
        scored = iq_engine.score_iq(dict(final_scores), question_set=question_set)
        return {
            gap.key: gap for gap in targets_engine.iq_targets(scored, targets, question_set).items
        }
    except ScoringError:
        return {}


def predecessor(db: Session, row: DimensionTargets) -> DimensionTargets | None:
    """The change before ``row`` on the same scale."""
    return db.scalars(
        select(DimensionTargets)
        .where(
            DimensionTargets.organisation_id == row.organisation_id,
            DimensionTargets.scale == row.scale,
            (DimensionTargets.created_at < row.created_at)
            | ((DimensionTargets.created_at == row.created_at) & (DimensionTargets.id < row.id)),
        )
        .order_by(DimensionTargets.created_at.desc(), DimensionTargets.id.desc())
        .limit(1)
    ).first()
