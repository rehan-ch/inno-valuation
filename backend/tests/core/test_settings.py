"""Settings refuse a weak secret key outside development and test."""

import pytest
from pydantic import ValidationError

from app.core.settings import DEFAULT_SECRET_KEY, Environment, Settings

STRONG_KEY = "x" * 32
LIVE_ORIGIN = "https://app.example.com"


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("secret_key", [DEFAULT_SECRET_KEY, "x" * 31])
def test_weak_secret_key_rejected_in_deployed_envs(
    environment: Environment, secret_key: str
) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            _env_file=None,
            environment=environment,
            secret_key=secret_key,
            frontend_origin=LIVE_ORIGIN,
        )


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_strong_secret_key_accepted_in_deployed_envs(environment: Environment) -> None:
    settings = Settings(
        _env_file=None,
        environment=environment,
        secret_key=STRONG_KEY,
        frontend_origin=LIVE_ORIGIN,
    )
    assert settings.secret_key == STRONG_KEY


@pytest.mark.parametrize("environment", ["development", "test"])
def test_default_secret_key_allowed_locally(environment: Environment) -> None:
    settings = Settings(_env_file=None, environment=environment)
    assert settings.secret_key == DEFAULT_SECRET_KEY


def test_environment_defaults_to_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "https://localhost:3000",
        "https://127.0.0.1",
        "https://app.localhost",
        "http://app.example.com",
        "https://app.example.com/path",
        "app.example.com",
    ],
)
def test_unsafe_frontend_origin_rejected_in_deployed_envs(
    environment: Environment, origin: str
) -> None:
    with pytest.raises(ValidationError, match="FRONTEND_ORIGIN"):
        Settings(
            _env_file=None, environment=environment, secret_key=STRONG_KEY, frontend_origin=origin
        )


@pytest.mark.parametrize("origin", ["https://app.example.com", "https://app.example.com/"])
def test_https_frontend_origin_accepted_in_production(origin: str) -> None:
    settings = Settings(
        _env_file=None, environment="production", secret_key=STRONG_KEY, frontend_origin=origin
    )
    # Stored without the trailing slash, so CORS and the origin check see one value.
    assert settings.frontend_origin == LIVE_ORIGIN


def test_frontend_origin_trailing_slash_dropped_locally() -> None:
    settings = Settings(
        _env_file=None, environment="development", frontend_origin="http://localhost:3000/"
    )
    assert settings.frontend_origin == "http://localhost:3000"


def test_local_frontend_origin_allowed_in_development() -> None:
    settings = Settings(_env_file=None, environment="development")
    assert settings.frontend_origin.startswith("http://localhost")
