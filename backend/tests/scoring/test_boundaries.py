"""The scoring engine is pure: it must not import persistence, AI or HTTP code."""

import ast
from pathlib import Path

import pytest

import app.scoring

SCORING_DIR = Path(app.scoring.__file__).resolve().parent
FORBIDDEN = ("sqlalchemy", "app.models", "app.db", "app.ai", "httpx", "requests")


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative import inside app.scoring stays inside the package.
                continue
            base = node.module or ""
            modules.append(base)
            # "from app import db" style imports.
            modules.extend(f"{base}.{alias.name}" for alias in node.names)
    return modules


def _is_forbidden(module: str) -> bool:
    return any(module == f or module.startswith(f + ".") for f in FORBIDDEN)


SCORING_FILES = sorted(SCORING_DIR.rglob("*.py"))


@pytest.mark.parametrize("path", SCORING_FILES, ids=lambda p: str(p.relative_to(SCORING_DIR)))
def test_scoring_file_has_no_forbidden_imports(path: Path) -> None:
    bad = [m for m in _imported_modules(path) if _is_forbidden(m)]
    assert not bad, f"{path.name} imports forbidden modules: {bad}"


def test_checker_catches_forbidden_imports(tmp_path: Path) -> None:
    sample = tmp_path / "bad.py"
    sample.write_text("import sqlalchemy.orm\nfrom app import db\nfrom app.ai.client import x\n")
    assert [m for m in _imported_modules(sample) if _is_forbidden(m)] == [
        "sqlalchemy.orm",
        "app.db",
        "app.ai.client",
        "app.ai.client.x",
    ]
