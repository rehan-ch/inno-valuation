"""Database constraints and foreign key behaviour of the readiness tables.

The database itself must refuse an answer outside 1 to 5 (whole numbers only), a second
response per person, a second consensus or result per assessment, and an unknown status.
"""

from typing import Any

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.models import (
    ReadinessAssessment,
    ReadinessConsensus,
    ReadinessResponse,
    ReadinessResult,
    User,
)
from app.models.enums import ReadinessStatus
from tests.factories import (
    ReadinessAssessmentFactory,
    ReadinessConsensusFactory,
    ReadinessResponseFactory,
    ReadinessResultFactory,
    UserFactory,
)
from tests.models.test_accounts import _insert, expect_violation


def test_assessment_defaults(db: Session) -> None:
    assessment = ReadinessAssessmentFactory.create()
    assert assessment.status is ReadinessStatus.DRAFT
    assert assessment.weights_snapshot is None
    assert assessment.started_at is None
    assert assessment.finalised_at is None


def test_valid_answers_are_accepted(db: Session) -> None:
    response = ReadinessResponseFactory.create(answers={"cj_1": 1, "cj_2": 5, "bm_1": 3})
    db.flush()
    assert response.answers["cj_2"] == 5


@pytest.mark.parametrize("bad", [0, 6, 2.5, "3", True, None, [3]])
def test_response_answers_outside_the_scale_are_refused(db: Session, bad: Any) -> None:
    with expect_violation(db, "ck_readiness_responses_answers_1_to_5"):
        ReadinessResponseFactory.create(answers={"cj_1": bad})


def test_consensus_answers_outside_the_scale_are_refused(db: Session) -> None:
    with expect_violation(db, "ck_readiness_consensus_answers_1_to_5"):
        ReadinessConsensusFactory.create(answers={"cj_1": 0})


def test_one_response_per_person_per_assessment(db: Session) -> None:
    first = ReadinessResponseFactory.create()
    with expect_violation(db, "uq_readiness_responses_assessment_id_user_id"):
        ReadinessResponseFactory.create(
            assessment=first.assessment,
            organisation_id=first.organisation_id,
            user=first.user,
        )


def test_one_consensus_and_one_result_per_assessment(db: Session) -> None:
    # The second row goes in with raw SQL: assigning the one-to-one relationship
    # through the ORM would quietly steal the assessment from the first row.
    consensus = ReadinessConsensusFactory.create()
    db.flush()
    with expect_violation(db, "uq_readiness_consensus_assessment_id"):
        _insert(
            db,
            "readiness_consensus",
            organisation_id=consensus.organisation_id,
            assessment_id=consensus.assessment_id,
        )
    result = ReadinessResultFactory.create(per_dimension={"cj": 10}, total=120)
    db.flush()
    with expect_violation(db, "uq_readiness_results_assessment_id"):
        _insert(
            db,
            "readiness_results",
            organisation_id=result.organisation_id,
            assessment_id=result.assessment_id,
            per_dimension="{}",
            category_scores="{}",
            total=0,
            band_key="foundation",
            priorities="[]",
        )


def test_result_total_is_bounded(db: Session) -> None:
    with expect_violation(db, "ck_readiness_results_total_0_to_300"):
        ReadinessResultFactory.create(total=301)


def test_status_outside_the_enum_is_refused(db: Session) -> None:
    assessment = ReadinessAssessmentFactory.create()
    db.flush()
    with expect_violation(db, "ck_readiness_assessments_readiness_status"):
        db.execute(
            text("UPDATE readiness_assessments SET status = 'archived' WHERE id = :id"),
            {"id": assessment.id},
        )


def test_everything_under_an_assessment_dies_with_it(db: Session) -> None:
    response = ReadinessResponseFactory.create(answers={"cj_1": 4})
    assessment = response.assessment
    ReadinessConsensusFactory.create(
        assessment=assessment, organisation_id=assessment.organisation_id
    )
    ReadinessResultFactory.create(assessment=assessment, organisation_id=assessment.organisation_id)
    db.flush()

    db.execute(delete(ReadinessAssessment).where(ReadinessAssessment.id == assessment.id))

    for model in (ReadinessResponse, ReadinessConsensus, ReadinessResult):
        assert db.scalar(select(model)) is None


def test_a_deleted_participant_takes_their_answers_but_consensus_survives(db: Session) -> None:
    response = ReadinessResponseFactory.create(answers={"cj_1": 4})
    assessment = response.assessment
    facilitator = UserFactory.create()
    consensus = ReadinessConsensusFactory.create(
        assessment=assessment,
        organisation_id=assessment.organisation_id,
        set_by_user_id=facilitator.id,
    )
    db.flush()

    db.execute(delete(User).where(User.id == response.user_id))
    db.execute(delete(User).where(User.id == facilitator.id))
    db.expire_all()

    assert db.scalar(select(ReadinessResponse)) is None
    survivor = db.scalar(select(ReadinessConsensus))
    assert survivor is not None
    assert survivor.id == consensus.id
    assert survivor.set_by_user_id is None
