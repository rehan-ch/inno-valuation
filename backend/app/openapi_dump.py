"""Print the API's OpenAPI schema as JSON, the contract the frontend types are generated from.

    uv run python -m app.openapi_dump > ../frontend/openapi.json

The output is deterministic (sorted keys, two-space indent, trailing newline) and does not
depend on the shell or on .env: the environment and app version are pinned before the app
is built, so every machine and CI produce the same bytes. The app never serves requests here.
"""

import json
import os
import sys
from typing import Any

from fastapi import FastAPI

from app.core.settings import Settings, get_settings

# The schema only describes routes and models, so any environment builds the same one.
# Development is pinned because production refuses to start without a real SECRET_KEY.
DUMP_ENVIRONMENT = "development"


def render(app: FastAPI) -> str:
    """Serialise the app's OpenAPI schema in the committed, stable format."""
    schema: dict[str, Any] = app.openapi()
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _pin_settings() -> None:
    os.environ["ENVIRONMENT"] = DUMP_ENVIRONMENT
    os.environ["APP_VERSION"] = str(Settings.model_fields["app_version"].default)
    get_settings.cache_clear()


def main() -> None:
    _pin_settings()
    # Imported after pinning: app.main builds an app at import time, which reads settings.
    from app.main import create_app  # noqa: PLC0415

    sys.stdout.write(render(create_app()))


if __name__ == "__main__":
    main()
