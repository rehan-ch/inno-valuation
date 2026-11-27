"""Advice under real concurrency: every request on its own session and connection.

The ``db`` fixture shares one session, so it cannot show races. These tests commit to the
test database and remove everything they created afterwards.
"""

import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.jobs.db import override_task_session
from app.jobs.tasks.ai import run_ai
from app.models import (
    AiRun,
    AuditEvent,
    Interpretation,
    Organisation,
    Recommendation,
    SignInThrottle,
    User,
)
from app.models.enums import AiRunStatus, MembershipRole
from tests import factories
from tests.api.flows import READINESS, as_user, finish_readiness
from tests.api.helpers import csrf, member

PARTS = 4


@dataclass(frozen=True)
class World:
    first: TestClient
    second: TestClient
    url: str
    organisation_id: uuid.UUID
    # Ids of the runs an ask queued, in order. Nothing runs until a test runs it.
    queued: list[str]
    session: Callable[[], Session]


@pytest.fixture
def world(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    # Imported late on purpose: ENVIRONMENT=test must be set before the app loads.
    from app.main import app  # noqa: PLC0415

    def new_session() -> Session:
        return Session(db_engine, autoflush=False, expire_on_commit=False)

    def _get_db() -> Iterator[Session]:
        with new_session() as session:
            yield session

    @contextmanager
    def _task_session() -> Iterator[Session]:
        with new_session() as session:
            yield session

    # As with a real broker: an ask returns with its runs still queued.
    queued: list[str] = []
    monkeypatch.setattr(run_ai, "delay", queued.append)
    app.dependency_overrides[get_db] = _get_db
    override_task_session(_task_session)
    setup = new_session()
    factories.bind_session(setup)
    owner, org = member(MembershipRole.OWNER)
    mate, _ = member(MembershipRole.MEMBER, org)
    setup.commit()
    try:
        with TestClient(app) as first, TestClient(app) as second:
            as_user(first, owner, org)
            assessment_id = finish_readiness(first)
            as_user(second, mate, org)
            yield World(
                first,
                second,
                f"{READINESS}/assessments/{assessment_id}/advice",
                org.id,
                queued,
                new_session,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        override_task_session(None)
        factories.bind_session(None)
        setup.close()
        with new_session() as session:
            people = [owner.id, mate.id]
            session.execute(
                delete(AuditEvent).where(
                    or_(AuditEvent.organisation_id == org.id, AuditEvent.actor_user_id.in_(people))
                )
            )
            # Signing in counted against this machine's address; no other test commits one.
            session.execute(delete(SignInThrottle))
            session.execute(delete(Organisation).where(Organisation.id == org.id))
            session.execute(delete(User).where(User.id.in_(people)))
            session.commit()


def together(*calls: Callable[[], Any]) -> list[Any]:
    """Run the calls at the same moment, each on its own thread; an error is re-raised."""
    barrier = threading.Barrier(len(calls))
    out: list[Any] = [None] * len(calls)
    errors: list[BaseException] = []

    def go(index: int) -> None:
        barrier.wait()
        try:
            out[index] = calls[index]()
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=go, args=(index,)) for index in range(len(calls))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    if errors:
        raise errors[0]
    return out


def _count(world: World, model: type[Any]) -> int:
    with world.session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _ask(world: World, client: TestClient) -> Callable[[], Any]:
    headers = csrf(client)
    return lambda: client.post(world.url, json={}, headers=headers)


def test_two_people_asking_at_once_get_one_run_per_part(world: World) -> None:
    before = _count(world, AiRun)
    answers = together(_ask(world, world.first), _ask(world, world.second))
    assert [answer.status_code for answer in answers] == [200, 200]
    assert _count(world, AiRun) - before == PARTS
    assert len(world.queued) == PARTS


def test_a_message_delivered_twice_at_once_calls_the_model_once(world: World) -> None:
    assert _ask(world, world.first)().status_code == 200
    for run_id in world.queued:
        together(partial(run_ai, run_id), partial(run_ai, run_id))
    with world.session() as session:
        runs = session.scalars(select(AiRun).where(AiRun.id.in_(world.queued))).all()
        assert [(run.status, run.attempts) for run in runs] == [(AiRunStatus.SUCCEEDED, 1)] * PARTS


def test_many_readers_at_once_copy_the_finished_advice_once(world: World) -> None:
    assert _ask(world, world.first)().status_code == 200
    for run_id in world.queued:
        run_ai(run_id)
    interpretations = _count(world, Interpretation)
    recommendations = _count(world, Recommendation)
    answers = together(
        *[lambda: world.first.get(world.url), lambda: world.second.get(world.url)] * 4
    )
    assert [answer.status_code for answer in answers] == [200] * 8
    versions = {
        (answer.json()["interpretation"]["version"], answer.json()["recommendations"]["version"])
        for answer in answers
    }
    assert versions == {(1, 1)}
    assert _count(world, Interpretation) - interpretations == 1
    assert _count(world, Recommendation) - recommendations == 5  # one per priority


def test_a_read_takes_the_advice_lock_before_it_fails_a_stale_run(world: World) -> None:
    """An ask takes the organisation's advice lock, then a run's row. A read that failed a
    stale run first (its row) and then copied finished advice (the lock) could deadlock with
    it and answer 500. So while an ask holds the lock, a read must hold no run's row."""
    assert _ask(world, world.first)().status_code == 200
    # Three parts finish and wait to be copied; one run is lost and goes stale.
    lost, *finished = world.queued
    for run_id in finished:
        run_ai(run_id)
    with world.session() as session:
        session.execute(
            update(AiRun)
            .where(AiRun.id == lost)
            .values(created_at=datetime.now(UTC) - timedelta(days=1))
        )
        session.commit()

    answers: list[Any] = []
    with world.session() as asking:
        # An ask in progress: it holds the advice lock.
        asking.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"advice:{world.organisation_id}"},
        )
        reader = threading.Thread(target=lambda: answers.append(world.first.get(world.url)))
        reader.start()
        reader.join(timeout=1)
        assert reader.is_alive(), "the read must wait for the advice lock"
        # The ask can still take the stale run's row at once: the read does not hold it.
        asking.execute(select(AiRun.id).where(AiRun.id == lost).with_for_update(nowait=True))
        asking.commit()
    reader.join(timeout=30)
    assert [answer.status_code for answer in answers] == [200]
    # The lost run was the first part; the read failed it and copied the finished advice.
    body = answers[0].json()
    assert (body["interpretation"]["status"], body["recommendations"]["status"]) == (
        "failed",
        "ready",
    )
    with world.session() as session:
        statuses = session.scalars(select(AiRun.status).where(AiRun.id == lost)).all()
        assert statuses == [AiRunStatus.FAILED]
