"""Application settings, read from the environment and from .env files.

Lookup order (later wins): defaults below, ``../.env`` (repo root), ``.env`` (backend/),
then real environment variables. Defaults match the local docker-compose services so
tests run without any .env file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

Environment = Literal["development", "test", "staging", "production"]

# Environments that serve real users over HTTPS: secure cookies, real email, strong secret.
DEPLOYED_ENVIRONMENTS = frozenset({"staging", "production"})

# Placeholder, not a secret: the validator refuses it outside development and test.
DEFAULT_SECRET_KEY = "change-me-in-production"  # noqa: S105
MIN_SECRET_KEY_LENGTH = 32

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})  # noqa: S104


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Defaults to production so a deploy that forgets ENVIRONMENT still gets the
    # secret key check. Local scripts (bin/dev, bin/setup, bin/check) and the test
    # suite set development or test themselves.
    environment: Environment = "production"
    app_version: str = "0.1.0"

    database_url: str = (
        "postgresql+psycopg://innovaluation:innovaluation@localhost:5440/innovaluation"
    )
    # Only the server part (host, port, credentials) is used: the test suite creates and
    # drops its own throwaway database on that server.
    test_database_url: str = (
        "postgresql+psycopg://innovaluation:innovaluation@localhost:5440/innovaluation_test"
    )
    redis_url: str = "redis://localhost:6390/0"

    secret_key: str = DEFAULT_SECRET_KEY
    frontend_origin: str = "http://localhost:3000"

    anthropic_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    resend_api_key: str = ""
    email_from: str = "InnoValuation <noreply@localhost>"
    # The local mail catcher (Mailpit, from docker-compose) that development emails are
    # delivered to when there is no Resend key. Never used deployed.
    dev_smtp_host: str = "localhost"
    dev_smtp_port: int = 1026
    # Mailpit's web address, and whether each development email opens there in a new
    # browser tab as soon as it is sent (set DEV_EMAIL_OPEN_BROWSER=false to stop it).
    dev_mail_web_url: str = "http://localhost:8025"
    dev_email_open_browser: bool = True

    # Sessions. A session lasts a fixed time from sign-in; switching organisation keeps
    # the original end time.
    session_lifetime_days: int = Field(default=7, ge=1, le=30)
    # The version of the terms of use a new account accepts. Change it when the terms change.
    terms_version: str = "2026-10-13"

    @field_validator("frontend_origin")
    @classmethod
    def _normalise_frontend_origin(cls, value: str) -> str:
        """An origin has no trailing slash. One is easy to paste in, so it is dropped here,
        once, and CORS, the origin check and email links all see the same value."""
        return value.strip().rstrip("/")

    @model_validator(mode="after")
    def _check_secret_key(self) -> "Settings":
        if self.is_deployed and (
            self.secret_key == DEFAULT_SECRET_KEY or len(self.secret_key) < MIN_SECRET_KEY_LENGTH
        ):
            raise ValueError(
                f"SECRET_KEY must be set to a non-default value of at least "
                f"{MIN_SECRET_KEY_LENGTH} characters in {self.environment}. "
                "For local work, set ENVIRONMENT=development in .env."
            )
        return self

    @model_validator(mode="after")
    def _check_frontend_origin(self) -> "Settings":
        """Deployed sites need an https frontend origin that is not this machine.

        The origin is the only browser origin allowed to make unsafe requests, and email
        links point at it, so a local or plain-http value there would be a security hole.
        """
        if not self.is_deployed:
            return self
        url = urlsplit(self.frontend_origin)
        host = (url.hostname or "").lower()
        if (
            url.scheme != "https"
            or not host
            or host in LOCAL_HOSTS
            or host.endswith(".localhost")
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            raise ValueError(
                f"FRONTEND_ORIGIN must be an https origin that is not localhost in "
                f"{self.environment}, for example https://app.example.com."
            )
        return self

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def is_deployed(self) -> bool:
        """Staging or production: real users, HTTPS, real email."""
        return self.environment in DEPLOYED_ENVIRONMENTS


@lru_cache
def get_settings() -> Settings:
    return Settings()
