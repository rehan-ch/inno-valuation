"""Shared fixtures.

ENVIRONMENT is forced to "test" before any app module is imported, so Celery runs eagerly.
Database fixtures are lazy and opt-in: tests that do not request ``db`` or ``client``
(for example tests/scoring) never touch Postgres.
"""

import os

os.environ["ENVIRONMENT"] = "test"

from collections.abc import Iterator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.deps import get_db
from tests import factories
from tests.database import alembic_config, throwaway_database


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Create a throwaway database on TEST_DATABASE_URL's server, migrate it, drop it after."""
    with throwaway_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture(scope="session")
def db_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    """A session inside an outer transaction that is rolled back after the test.

    Service code may call ``commit()``; it only releases a savepoint.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    factories.bind_session(session)
    try:
        yield session
    finally:
        factories.bind_session(None)
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    # Imported late on purpose: ENVIRONMENT=test must be set before the app loads.
    from app.main import app  # noqa: PLC0415

    def _override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
