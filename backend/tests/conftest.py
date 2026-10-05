"""Shared fixtures.

ENVIRONMENT is forced to "test" before any app module is imported, so Celery runs eagerly.
Database fixtures are lazy and opt-in: tests that do not request ``db`` or ``client``
(for example tests/scoring) never touch Postgres.
"""

import os

os.environ["ENVIRONMENT"] = "test"

import uuid  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.deps import get_db  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from tests import factories  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Create a throwaway database on TEST_DATABASE_URL's server, migrate it, drop it after."""
    base_url = make_url(get_settings().test_database_url)
    name = f"innovaluation_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(
        base_url.set(database="postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True
    )
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
        url = base_url.set(database=name).render_as_string(hide_password=False)
        try:
            cfg = Config(str(BACKEND_DIR / "alembic.ini"))
            cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
            cfg.attributes["database_url"] = url
            cfg.attributes["configure_logger"] = False
            command.upgrade(cfg, "head")
            yield url
        finally:
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


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
    from app.main import app

    def _override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
