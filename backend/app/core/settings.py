"""Application settings, read from the environment and from .env files.

Lookup order (later wins): defaults below, ``../.env`` (repo root), ``.env`` (backend/),
then real environment variables. Defaults match the local docker-compose services so
tests run without any .env file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

Environment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = "development"
    app_version: str = "0.1.0"

    database_url: str = (
        "postgresql+psycopg://innovaluation:innovaluation@localhost:5440/innovaluation"
    )
    test_database_url: str = (
        "postgresql+psycopg://innovaluation:innovaluation@localhost:5440/innovaluation_test"
    )
    redis_url: str = "redis://localhost:6390/0"

    secret_key: str = "change-me-in-production"
    frontend_origin: str = "http://localhost:3000"

    anthropic_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    resend_api_key: str = ""
    email_from: str = "InnoValuation <noreply@localhost>"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
