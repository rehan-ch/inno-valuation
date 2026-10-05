"""Settings refuse a weak secret key outside development and test."""

import pytest
from pydantic import ValidationError

from app.core.settings import DEFAULT_SECRET_KEY, Settings

STRONG_KEY = "x" * 32


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("secret_key", [DEFAULT_SECRET_KEY, "x" * 31])
def test_weak_secret_key_rejected_in_deployed_envs(environment: str, secret_key: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None, environment=environment, secret_key=secret_key)  # type: ignore[call-arg]


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_strong_secret_key_accepted_in_deployed_envs(environment: str) -> None:
    settings = Settings(_env_file=None, environment=environment, secret_key=STRONG_KEY)  # type: ignore[call-arg]
    assert settings.secret_key == STRONG_KEY


@pytest.mark.parametrize("environment", ["development", "test"])
def test_default_secret_key_allowed_locally(environment: str) -> None:
    settings = Settings(_env_file=None, environment=environment)  # type: ignore[call-arg]
    assert settings.secret_key == DEFAULT_SECRET_KEY
