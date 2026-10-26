"""Explanations under real concurrency: separate sessions on separate connections.

The ``db`` fixture shares one session, so it cannot show races. These tests commit to the
test database and remove everything they created afterwards.
"""

import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.ai.client import AiReply, AiRequest, override_ai_client
from app.ai.config import get_ai_config
from app.core.errors import AppError
from app.core.permissions import OrgContext, OrgRole
from app.jobs.db import override_task_session
from app.jobs.tasks.ai import SKIPPED, run_ai
from app.models import AiRun, Membership, Organisation, User
from app.models.enums import AiRunStatus, AiTouchpoint, MembershipRole
from app.scoring.question_set import QUESTION_SET
from app.services import explanations
from tests.ai.support import reply

SETTINGS = get_ai_config().touchpoint(AiTouchpoint.EXPLAIN_QUESTION)

GOOD = {
    "dimension_key": "customer_journey",
    "explanation": [
        "This question asks how well you know your customers.",
        "It covers every step they take with you.",
    ],
    "example": "A shop maps each step from first visit to repeat purchase.",
}


@dataclass(frozen=True)
class World:
    org_id: uuid.UUID
    user_id: uuid.UUID


@pytest.fixture
def world(db_engine: Engine) -> Iterator[World]:
    suffix = uuid.uuid4().hex[:10]
    with Session(db_engine) as session:
        org = Organisation(name=f"Race {suffix}")
        user = User(email=f"owner-{suffix}@example.com", name="Owner", password_hash="x")
        session.add_all([org, user])
        session.flush()
        session.add(Membership(organisation_id=org.id, user_id=user.id, role=MembershipRole.OWNER))
        session.commit()
        built = World(org.id, user.id)
    try:
        yield built
    finally:
        with Session(db_engine) as session:
            session.execute(delete(Organisation).where(Organisation.id == built.org_id))
            session.execute(delete(User).where(User.id == built.user_id))
            session.commit()


@pytest.fixture
def _tasks_on_their_own_sessions(db_engine: Engine) -> Iterator[None]:
    """The eager Celery task opens a session on the test database, as a worker would."""

    def factory() -> Session:
        return Session(db_engine)

    override_task_session(factory)
    try:
        yield
    finally:
        override_task_session(None)


def _ctx(session: Session, world: World) -> OrgContext:
    org = session.get(Organisation, world.org_id)
    user = session.get(User, world.user_id)
    assert org is not None
    assert user is not None
    return OrgContext(organisation=org, user=user, role=OrgRole.OWNER)


def _run_together(*actions: Callable[[], object]) -> list[object]:
    """Run each action in its own thread, released at the same moment. Returns each
    result, or the exception it raised."""
    results: list[object] = [None] * len(actions)
    start = threading.Barrier(len(actions))

    def run(index: int) -> None:
        start.wait()
        try:
            results[index] = actions[index]()
        except Exception as error:
            results[index] = error

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(actions))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def _count(db_engine: Engine, world: World) -> int:
    with Session(db_engine) as session:
        return int(
            session.scalar(
                select(func.count()).select_from(AiRun).where(AiRun.organisation_id == world.org_id)
            )
            or 0
        )


def _queued_run(db_engine: Engine, world: World) -> uuid.UUID:
    with Session(db_engine) as session:
        run = AiRun(
            organisation_id=world.org_id,
            touchpoint=AiTouchpoint.EXPLAIN_QUESTION,
            subject_type="readiness_question",
            subject_id=f"{QUESTION_SET.version}:customer_journey_1",
            model=SETTINGS.model,
            effort="low",
            prompt_version="1",
            system_prompt="system",
            user_prompt="user",
        )
        session.add(run)
        session.commit()
        return run.id


@pytest.mark.usefixtures("_tasks_on_their_own_sessions")
def test_the_daily_limit_holds_across_questions_asked_at_once(
    db_engine: Engine, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(explanations, "DAILY_LIMIT", 150)
    with Session(db_engine) as session:
        session.add_all(
            AiRun(
                organisation_id=world.org_id,
                touchpoint=AiTouchpoint.EXPLAIN_QUESTION,
                subject_type="readiness_question",
                subject_id=f"{QUESTION_SET.version}:customer_journey_1",
                status=AiRunStatus.FAILED,
                model=SETTINGS.model,
                effort="low",
                prompt_version="1",
                system_prompt="system",
                user_prompt="user",
            )
            for _ in range(149)
        )
        session.commit()

    def ask(question_id: str) -> Callable[[], object]:
        def _ask() -> object:
            with Session(db_engine) as session:
                run = explanations.request(
                    session, _ctx(session, world), QUESTION_SET.version, question_id
                )
                return run.status

        return _ask

    first, second = _run_together(ask("customer_journey_1"), ask("customer_journey_2"))
    outcomes = sorted(
        "refused" if isinstance(r, AppError) and r.code == "too_many_requests" else "asked"
        for r in (first, second)
    )
    assert outcomes == ["asked", "refused"], (first, second)
    assert _count(db_engine, world) == 150


class _SlowAiClient:
    """Answers once the test says so, so a second delivery arrives mid-call."""

    offline = False

    def __init__(self) -> None:
        self.release = threading.Event()
        self.called = threading.Event()
        self.calls = 0

    def complete(self, request: AiRequest) -> AiReply:
        self.calls += 1
        self.called.set()
        assert self.release.wait(timeout=30)
        return reply(GOOD)


@pytest.mark.usefixtures("_tasks_on_their_own_sessions")
def test_two_deliveries_of_one_run_call_the_ai_once(db_engine: Engine, world: World) -> None:
    run_id = _queued_run(db_engine, world)
    ai = _SlowAiClient()
    override_ai_client(ai)
    try:
        first = threading.Thread(target=run_ai, args=(str(run_id),))
        first.start()
        assert ai.called.wait(timeout=30), "the first delivery must reach the model"
        assert run_ai(str(run_id)) == SKIPPED  # the second delivery, mid-call
        ai.release.set()
        first.join(timeout=30)
    finally:
        override_ai_client(None)
    assert ai.calls == 1
    with Session(db_engine) as session:
        run = session.get(AiRun, run_id)
        assert run is not None
        assert run.status is AiRunStatus.SUCCEEDED
        assert run.response_json == GOOD
        assert run.started_at is not None
        assert run.started_at <= datetime.now(UTC)
