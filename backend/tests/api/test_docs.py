"""API docs and the OpenAPI schema are served in development and test only."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.settings import Environment, Settings

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")
STRONG_KEY = "k" * 32
LIVE_ORIGIN = "https://app.example.com"


def _client_for(environment: Environment, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(
        _env_file=None,
        environment=environment,
        secret_key=STRONG_KEY,
        frontend_origin=LIVE_ORIGIN,
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return TestClient(main.create_app())


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_hidden_when_deployed(
    environment: Environment, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = _client_for(environment, monkeypatch).get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("environment", ["development", "test"])
@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_served_locally(
    environment: Environment, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _client_for(environment, monkeypatch).get(path).status_code == 200


def test_schema_still_builds_when_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        secret_key=STRONG_KEY,
        frontend_origin=LIVE_ORIGIN,
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    # The openapi dump calls app.openapi() directly, so it must work without the route.
    assert main.create_app().openapi()["info"]["title"] == "InnoValuation API"
