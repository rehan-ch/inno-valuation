"""Read side of Phase 5: what the dashboard, the compass, the drill-down and the history
show (spec 4, 6, 7, 9).

Nothing here scores anything. It loads final readiness results and confirmed IQ
assessments as they were written, and asks the engine for the two things that depend on
more than one record: the gap to a target (``app.scoring.targets``) and the change between
two results on the same question set version (``app.scoring.trend``).

Readiness and IQ are loaded by separate functions and never meet in one number (spec 4).
A consultant sees what the other readers see here: only final results and confirmed
assessments are ever loaded.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import OrgContext
from app.models import (
    Idea,
    IqAssessment,
    IqDimensionScore,
    ReadinessAssessment,
    ReadinessConsensus,
    ReadinessResult,
)
from app.models.enums import IqAssessmentStatus, ReadinessStatus, TargetScale
from app.scoring import trend
from app.scoring.errors import ScoringError
from app.scoring.question_set import QuestionSet, question_set_for
from app.scoring.targets import TargetGap
from app.scoring.trend import Change, DimensionChange
from app.services import targets as targets_service


def _not_found() -> AppError:
    return AppError("not_found", "Not found.", 404)


def available_question_set(version: int) -> QuestionSet | None:
    """The question set of ``version``, or None when this server does not have it: such a
    result is left out of the dashboard instead of breaking it."""
    try:
        return question_set_for(version)
    except ScoringError:
        return None


# Readiness


@dataclass(frozen=True, slots=True)
class ReadinessRecord:
    """One final readiness result as it was written, with what is needed to show it."""

    assessment: ReadinessAssessment
    result: ReadinessResult
    finalised_at: datetime
    question_set: QuestionSet
    # The team's agreed answers (Amy Q5); None if the row is gone.
    agreed_answers: Mapping[str, Any] | None
    gaps: Mapping[str, TargetGap]

    @property
    def scores(self) -> dict[str, int]:
        return {key: int(value) for key, value in self.result.per_dimension.items()}


def readiness_records(db: Session, ctx: OrgContext) -> list[ReadinessRecord]:
    """Every final readiness result of the organisation, newest first, each with its gaps
    to today's targets."""
    rows = db.execute(
        select(ReadinessAssessment, ReadinessResult)
        .join(ReadinessResult, ReadinessResult.assessment_id == ReadinessAssessment.id)
        .where(
            ReadinessAssessment.organisation_id == ctx.organisation_id,
            ReadinessAssessment.status == ReadinessStatus.FINAL,
            ReadinessAssessment.finalised_at.is_not(None),
        )
        .order_by(ReadinessAssessment.finalised_at.desc(), ReadinessAssessment.id.desc())
    ).all()
    return _readiness_records(db, ctx.organisation_id, [(a, r) for a, r in rows])


def readiness_record(
    db: Session, assessment: ReadinessAssessment, result: ReadinessResult
) -> ReadinessRecord | None:
    """One final result, ready to show; None when its question set is not available."""
    found = _readiness_records(db, assessment.organisation_id, [(assessment, result)])
    return found[0] if found else None


def _readiness_records(
    db: Session,
    organisation_id: uuid.UUID,
    rows: Sequence[tuple[ReadinessAssessment, ReadinessResult]],
) -> list[ReadinessRecord]:
    if not rows:
        return []
    answers: dict[uuid.UUID, Mapping[str, Any]] = dict(
        db.execute(
            select(ReadinessConsensus.assessment_id, ReadinessConsensus.answers).where(
                ReadinessConsensus.assessment_id.in_([assessment.id for assessment, _ in rows])
            )
        ).all()
    )
    targets: dict[int, targets_service.Targets] = {}
    records = []
    for assessment, result in rows:
        question_set = available_question_set(assessment.question_set_version)
        if (
            question_set is None
            or assessment.finalised_at is None
            or set(result.per_dimension) != set(question_set.dimension_keys)
        ):
            continue
        if question_set.version not in targets:
            targets[question_set.version] = targets_service.current_targets(
                db, organisation_id, TargetScale.READINESS, question_set
            )
        agreed = answers.get(assessment.id)
        records.append(
            ReadinessRecord(
                assessment=assessment,
                result=result,
                finalised_at=assessment.finalised_at,
                question_set=question_set,
                agreed_answers=agreed,
                gaps=targets_service.readiness_gaps(
                    targets[question_set.version], agreed, result.per_dimension, question_set
                ),
            )
        )
    return records


# IQ


@dataclass(frozen=True, slots=True)
class IqRecord:
    """One confirmed IQ assessment as it was written, with what is needed to show it."""

    idea: Idea
    assessment: IqAssessment
    confirmed_at: datetime
    iq: Decimal
    question_set: QuestionSet
    rows: Mapping[str, IqDimensionScore]
    gaps: Mapping[str, TargetGap]

    @property
    def scores(self) -> dict[str, int]:
        return {
            key: int(row.final_score)
            for key, row in self.rows.items()
            if row.final_score is not None
        }


def iq_record(db: Session, idea: Idea, assessment: IqAssessment) -> IqRecord | None:
    """One confirmed assessment, ready to show; None when it is not confirmed or its
    question set is not available."""
    if assessment.status is not IqAssessmentStatus.CONFIRMED:
        return None
    found = _iq_records(db, assessment.organisation_id, [(idea, assessment)])
    return found[0] if found else None


def _iq_records(
    db: Session, organisation_id: uuid.UUID, pairs: Sequence[tuple[Idea, IqAssessment]]
) -> list[IqRecord]:
    if not pairs:
        return []
    by_assessment: dict[uuid.UUID, dict[str, IqDimensionScore]] = {}
    for row in db.scalars(
        select(IqDimensionScore).where(
            IqDimensionScore.assessment_id.in_([assessment.id for _, assessment in pairs])
        )
    ):
        by_assessment.setdefault(row.assessment_id, {})[row.dimension_key] = row
    targets: dict[int, targets_service.Targets] = {}
    records = []
    for idea, assessment in pairs:
        question_set = available_question_set(assessment.question_set_version)
        rows = by_assessment.get(assessment.id, {})
        if (
            question_set is None
            or assessment.iq is None
            or assessment.confirmed_at is None
            or set(rows) != set(question_set.dimension_keys)
            or any(row.final_score is None for row in rows.values())
        ):
            continue
        if question_set.version not in targets:
            targets[question_set.version] = targets_service.current_targets(
                db, organisation_id, TargetScale.IQ, question_set
            )
        final = {key: int(row.final_score or 0) for key, row in rows.items()}
        records.append(
            IqRecord(
                idea=idea,
                assessment=assessment,
                confirmed_at=assessment.confirmed_at,
                iq=assessment.iq,
                question_set=question_set,
                rows=rows,
                gaps=targets_service.iq_gaps(targets[question_set.version], final, question_set),
            )
        )
    return records


def latest_iq_records(db: Session, ctx: OrgContext) -> list[IqRecord]:
    """The newest confirmed assessment of every idea that is not archived, most recently
    confirmed first. A newer proposal still under review never hides or replaces it: only
    confirmed scores are shown (Amy Q1)."""
    newest = (
        select(IqAssessment)
        .ext(distinct_on(IqAssessment.idea_id))
        .join(Idea, Idea.id == IqAssessment.idea_id)
        .where(
            IqAssessment.organisation_id == ctx.organisation_id,
            IqAssessment.status == IqAssessmentStatus.CONFIRMED,
            Idea.organisation_id == ctx.organisation_id,
            Idea.archived_at.is_(None),
        )
        .order_by(IqAssessment.idea_id, IqAssessment.confirmed_at.desc(), IqAssessment.id.desc())
    )
    assessments = list(db.scalars(newest))
    if not assessments:
        return []
    ideas = {
        idea.id: idea
        for idea in db.scalars(select(Idea).where(Idea.id.in_([a.idea_id for a in assessments])))
    }
    records = _iq_records(db, ctx.organisation_id, [(ideas[a.idea_id], a) for a in assessments])
    return sorted(
        records,
        key=lambda r: (r.confirmed_at, str(r.assessment.id)),
        reverse=True,
    )


def idea_iq_records(db: Session, ctx: OrgContext, idea: Idea) -> list[IqRecord]:
    """Every confirmed assessment of one idea, newest first."""
    assessments = db.scalars(
        select(IqAssessment)
        .where(
            IqAssessment.idea_id == idea.id,
            IqAssessment.organisation_id == ctx.organisation_id,
            IqAssessment.status == IqAssessmentStatus.CONFIRMED,
        )
        .order_by(IqAssessment.confirmed_at.desc(), IqAssessment.id.desc())
    )
    return _iq_records(db, ctx.organisation_id, [(idea, assessment) for assessment in assessments])


def pick_idea(records: Sequence[IqRecord], idea_id: uuid.UUID | None) -> IqRecord | None:
    """The selected idea's record: the one asked for (404 when it is not among the ideas
    with a confirmed assessment), else the most recently confirmed, else None."""
    if idea_id is None:
        return records[0] if records else None
    for record in records:
        if record.idea.id == idea_id:
            return record
    raise _not_found()


# Change over time (spec 9). Only between results on the same question set version.


@dataclass(frozen=True, slots=True)
class ReadinessStep:
    record: ReadinessRecord
    compared_with: ReadinessRecord | None
    total: Change[int] | None
    dimensions: Mapping[str, DimensionChange]


def readiness_steps(records: Sequence[ReadinessRecord]) -> list[ReadinessStep]:
    """Each result (newest first, as given) beside the one before it on the same question
    set version, with the engine's change per dimension and on the total."""
    steps: list[ReadinessStep] = []
    for index, record in enumerate(records):
        earlier = next(
            (
                other
                for other in records[index + 1 :]
                if other.question_set.version == record.question_set.version
            ),
            None,
        )
        total: Change[int] | None = None
        dimensions: dict[str, DimensionChange] = {}
        if earlier is not None:
            try:
                dimensions = {
                    change.key: change
                    for change in trend.dimension_changes(
                        earlier.scores,
                        record.scores,
                        previous_version=earlier.question_set.version,
                        current_version=record.question_set.version,
                        question_set=record.question_set,
                    )
                }
                total = trend.whole_change(earlier.result.total, record.result.total)
            except ScoringError:
                earlier, total, dimensions = None, None, {}
        steps.append(
            ReadinessStep(record=record, compared_with=earlier, total=total, dimensions=dimensions)
        )
    return steps


@dataclass(frozen=True, slots=True)
class IqStep:
    record: IqRecord
    compared_with: IqRecord | None
    iq: Change[Decimal] | None
    # Only when both have a Value for Money in the same currency.
    vfm: Change[Decimal] | None
    dimensions: Mapping[str, DimensionChange]


def iq_steps(records: Sequence[IqRecord]) -> list[IqStep]:
    """Each confirmed assessment of one idea (newest first, as given) beside the one before
    it on the same question set version."""
    steps: list[IqStep] = []
    for index, record in enumerate(records):
        earlier = next(
            (
                other
                for other in records[index + 1 :]
                if other.question_set.version == record.question_set.version
            ),
            None,
        )
        iq: Change[Decimal] | None = None
        vfm: Change[Decimal] | None = None
        dimensions: dict[str, DimensionChange] = {}
        if earlier is not None:
            try:
                dimensions = {
                    change.key: change
                    for change in trend.dimension_changes(
                        earlier.scores,
                        record.scores,
                        previous_version=earlier.question_set.version,
                        current_version=record.question_set.version,
                        question_set=record.question_set,
                    )
                }
                iq = trend.decimal_change(earlier.iq, record.iq)
                if (
                    earlier.assessment.vfm_per_point is not None
                    and record.assessment.vfm_per_point is not None
                    and earlier.assessment.currency == record.assessment.currency
                ):
                    vfm = trend.decimal_change(
                        earlier.assessment.vfm_per_point, record.assessment.vfm_per_point
                    )
            except ScoringError:
                earlier, iq, vfm, dimensions = None, None, None, {}
        steps.append(
            IqStep(record=record, compared_with=earlier, iq=iq, vfm=vfm, dimensions=dimensions)
        )
    return steps
