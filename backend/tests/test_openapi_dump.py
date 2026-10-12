import json
import os
import subprocess
import sys
from pathlib import Path

from app.main import create_app
from app.openapi_dump import render

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _dump(**env: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "app.openapi_dump"],
        cwd=BACKEND_DIR,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return result.stdout


def test_render_is_valid_sorted_json_with_the_health_path() -> None:
    text = render(create_app())

    schema = json.loads(text)
    assert "/api/v1/health" in schema["paths"]
    assert "HealthOut" in schema["components"]["schemas"]
    assert text.endswith("}\n")
    assert text == json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_dump_is_the_same_in_every_environment() -> None:
    # Production with the default SECRET_KEY would refuse to start; the dump must not care.
    production = _dump(ENVIRONMENT="production", APP_VERSION="9.9.9")
    test = _dump(ENVIRONMENT="test")

    assert production == test
    assert "/api/v1/health" in json.loads(production)["paths"]
