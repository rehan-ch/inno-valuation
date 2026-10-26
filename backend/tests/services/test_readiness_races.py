"""Readiness saves under real concurrency: separate sessions on separate connections.

The ``db`` fixture shares one session, so it cannot show races. These tests commit to the
test database and remove everything they created afterwards.
"""

import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import OrgContext, OrgRole
from app.models import (
    AuditEvent,
    Membership,
    Organisation,
    ReadinessAssessment,
    ReadinessConsensus,
    ReadinessResponse,
    User,
)
from app.models.enums import MembershipRole, ReadinessStatus
from app.scoring.question_set import QUESTION_SET
from app.services import readiness

IDS = QUESTION_SET.all_question_ids()


@dataclass(frozen=True)
class World:
    org_id: uuid.UUID
    user_id: uuid.UUID
    assessment_id: uuid.UUID


@pytest.fixture
def world(db_engine: Engine) -> Iterator[World]:
    suffix = uuid.uuid4().hex[:10]
    with Session(db_engine) as session:
        org = Organisation(name=f"Race {suffix}")
        user = User(email=f"owner-{suffix}@example.com", name="Owner", password_hash="x")
        session.add_all([org, user])
        session.flush()
        session.add(Membership(organisation_id=org.id, user_id=user.id, role=MembershipRole.OWNER))
        assessment = ReadinessAssessment(
            organisation_id=org.id,
            question_set_version=QUESTION_SET.version,
            status=ReadinessStatus.COLLECTING,
            started_at=datetime.now(UTC),
        )
        session.add(assessment)
        session.flush()
        session.add(
            ReadinessResponse(
                organisation_id=org.id, assessment_id=assessment.id, user_id=user.id, answers={}
            )
        )
        session.commit()
        built = World(org.id, user.id, assessment.id)
    try:
        yield built
    finally:
        with Session(db_engine) as session:
            session.execute(delete(AuditEvent).where(AuditEvent.organisation_id == built.org_id))
            session.execute(delete(Organisation).where(Organisation.id == built.org_id))
            session.execute(delete(User).where(User.id == built.user_id))
            session.commit()


def _ctx(session: Session, world: World) -> OrgContext:
    org = session.get(Organisation, world.org_id)
    user = session.get(User, world.user_id)
    assert org is not None
    assert user is not None
    return OrgContext(organisation=org, user=user, role=OrgRole.OWNER)


def _hold_response_lock(session: Session, world: World, answers: dict[str, int]) -> None:
    """Session A: a save in progress, holding the response row and changing its answers."""
    response = session.scalar(
        select(ReadinessResponse)
        .where(ReadinessResponse.assessment_id == world.assessment_id)
        .with_for_update()
    )
    assert response is not None
    response.answers = {**response.answers, **answers}
    session.flush()


def test_two_saves_at_once_keep_both_answers(db_engine: Engine, world: World) -> None:
    errors: list[BaseException] = []

    def second_save() -> None:
        try:
            with Session(db_engine) as session_b:
                readiness.save_answers(
                    session_b, _ctx(session_b, world), world.assessment_id, {IDS[1]: 4}
                )
        except BaseException as error:
            errors.append(error)

    with Session(db_engine) as session_a:
        _hold_response_lock(session_a, world, {IDS[0]: 3})
        thread = threading.Thread(target=second_save)
        thread.start()
        thread.join(timeout=1)
        assert thread.is_alive(), "the second save must wait for the first one's row lock"
        session_a.commit()
    thread.join(timeout=10)
    assert not errors

    with Session(db_engine) as session:
        response = session.scalar(
            select(ReadinessResponse).where(ReadinessResponse.assessment_id == world.assessment_id)
        )
        assert response is not None
        assert response.answers == {IDS[0]: 3, IDS[1]: 4}


def test_submit_waits_for_a_save_in_flight(db_engine: Engine, world: World) -> None:
    errors: list[BaseException] = []

    def submit() -> None:
        try:
            with Session(db_engine) as session_b:
                readiness.submit_answers(session_b, _ctx(session_b, world), world.assessment_id)
        except BaseException as error:
            errors.append(error)

    with Session(db_engine) as session_a:
        # The last answers are still being saved when the person presses submit.
        _hold_response_lock(session_a, world, dict.fromkeys(IDS, 3))
        thread = threading.Thread(target=submit)
        thread.start()
        thread.join(timeout=1)
        assert thread.is_alive(), "submit must wait for the save's row lock"
        session_a.commit()
    thread.join(timeout=10)
    assert not errors  # counted all 60, not the stale empty answers

    with Session(db_engine) as session:
        response = session.scalar(
            select(ReadinessResponse).where(ReadinessResponse.assessment_id == world.assessment_id)
        )
        assert response is not None
        assert response.submitted_at is not None
        assert len(response.answers) == len(IDS)


def _hold_assessment_lock(session: Session, world: World, *, share: bool) -> ReadinessAssessment:
    """Session A: a status change (``FOR UPDATE``) or a submit (``FOR SHARE``) in flight."""
    assessment = session.scalar(
        select(ReadinessAssessment)
        .where(ReadinessAssessment.id == world.assessment_id)
        .with_for_update(read=share)
    )
    assert assessment is not None
    return assessment


def _fill_answers(db_engine: Engine, world: World) -> None:
    with Session(db_engine) as session:
        response = session.scalar(
            select(ReadinessResponse).where(ReadinessResponse.assessment_id == world.assessment_id)
        )
        assert response is not None
        response.answers = dict.fromkeys(IDS, 3)
        session.commit()


def test_begin_consensus_waits_for_a_submit_in_flight(db_engine: Engine, world: World) -> None:
    """A submit holds the share lock; agreeing waits for it and then counts that person."""
    _fill_answers(db_engine, world)
    errors: list[BaseException] = []

    def begin() -> None:
        try:
            with Session(db_engine) as session_b:
                readiness.begin_consensus(session_b, _ctx(session_b, world), world.assessment_id)
        except BaseException as error:
            errors.append(error)

    with Session(db_engine) as session_a:
        _hold_assessment_lock(session_a, world, share=True)
        response = session_a.scalar(
            select(ReadinessResponse).where(ReadinessResponse.assessment_id == world.assessment_id)
        )
        assert response is not None
        response.submitted_at = datetime.now(UTC)
        session_a.flush()
        thread = threading.Thread(target=begin)
        thread.start()
        thread.join(timeout=1)
        assert thread.is_alive(), "begin_consensus must wait for the submit's share lock"
        session_a.commit()
    thread.join(timeout=10)
    assert not errors  # the submission was counted, not refused as "no_submissions"

    with Session(db_engine) as session:
        consensus = session.scalar(
            select(ReadinessConsensus).where(
                ReadinessConsensus.assessment_id == world.assessment_id
            )
        )
        assert consensus is not None
        assert consensus.participant_count == 1


def test_a_submit_after_consensus_began_is_refused(db_engine: Engine, world: World) -> None:
    """Agreeing holds the update lock; a submit waits and then sees answering is closed."""
    _fill_answers(db_engine, world)
    errors: list[BaseException] = []

    def submit() -> None:
        try:
            with Session(db_engine) as session_b:
                readiness.submit_answers(session_b, _ctx(session_b, world), world.assessment_id)
        except BaseException as error:
            errors.append(error)

    with Session(db_engine) as session_a:
        assessment = _hold_assessment_lock(session_a, world, share=False)
        assessment.status = ReadinessStatus.CONSENSUS
        session_a.flush()
        thread = threading.Thread(target=submit)
        thread.start()
        thread.join(timeout=1)
        assert thread.is_alive(), "submit must wait for the status change's lock"
        session_a.commit()
    thread.join(timeout=10)
    assert len(errors) == 1
    assert isinstance(errors[0], AppError)
    assert errors[0].code == "wrong_status"

    with Session(db_engine) as session:
        response = session.scalar(
            select(ReadinessResponse).where(ReadinessResponse.assessment_id == world.assessment_id)
        )
        assert response is not None
        assert response.submitted_at is None


def test_two_starts_at_once_open_exactly_one_assessment(db_engine: Engine, world: World) -> None:
    """Both starts lock the organisation; the second one sees the first one's assessment."""
    with Session(db_engine) as session:
        assessment = session.get(ReadinessAssessment, world.assessment_id)
        assert assessment is not None
        assessment.status = ReadinessStatus.FINAL  # nothing open: both may try to start
        session.commit()
    ready = threading.Barrier(2)
    outcomes: list[str] = []

    def start() -> None:
        with Session(db_engine) as session:
            ctx = _ctx(session, world)
            ready.wait(timeout=5)
            try:
                readiness.start_assessment(session, ctx)
            except AppError as error:
                outcomes.append(error.code)
            else:
                outcomes.append("started")

    threads = [threading.Thread(target=start) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert sorted(outcomes) == ["assessment_open", "started"]

    with Session(db_engine) as session:
        open_ones = session.scalars(
            select(ReadinessAssessment.id).where(
                ReadinessAssessment.organisation_id == world.org_id,
                ReadinessAssessment.status != ReadinessStatus.FINAL,
            )
        ).all()
        assert len(open_ones) == 1
