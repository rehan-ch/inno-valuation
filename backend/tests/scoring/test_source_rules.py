"""Source rules for app/scoring: nothing hardcoded, every PENDING rule marked PROVISIONAL.

The marker rule also covers the readiness service, which applies two pending rules of its
own (which answers are required, and how priorities are ordered) when it finalises.
"""

import ast
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

import app.scoring
from tests.scoring.support import QS

SCORING_DIR = Path(app.scoring.__file__).resolve().parent
SOURCES = {p.name: p.read_text(encoding="utf-8") for p in sorted(SCORING_DIR.glob("*.py"))}

SERVICE_SOURCES = {
    "services/readiness.py": (SCORING_DIR.parent / "services" / "readiness.py").read_text(
        encoding="utf-8"
    )
}


def _methodology_words() -> set[str]:
    words: set[str] = set()
    for d in QS.dimensions:
        words |= {d.key, d.name}
    for c in QS.categories:
        words |= {c.key, c.name}
    for b in QS.readiness_bands:
        words |= {b.key, b.name}
    for lvl in QS.iq_levels:
        words |= {lvl.key, lvl.name}
    return words


def _string_literals(source: str) -> set[str]:
    """All string constants that are not docstrings."""
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_no_methodology_literal_in_code(name: str) -> None:
    words = _methodology_words()
    found = {s for s in _string_literals(SOURCES[name]) for w in words if w.lower() in s.lower()}
    assert not found, f"{name} hardcodes methodology text: {found}"


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_no_dimension_band_or_level_name_anywhere_in_source(name: str) -> None:
    """Multi-word names and snake_case keys must not appear even in comments or docstrings."""
    distinctive = {w for w in _methodology_words() if " " in w or "_" in w}
    found = {w for w in distinctive if w in SOURCES[name]}
    assert not found, f"{name} mentions {found}"


def test_the_checks_would_catch_a_hardcoded_key() -> None:
    sample = 'X = "customer_journey"\n'
    assert "customer_journey" in _string_literals(sample)
    assert "customer_journey" in _methodology_words()


EXPECTED_MARKERS = [
    ("_rounding.py", "ROUNDING = ROUND_HALF_UP  # PROVISIONAL: see open-questions Q18"),
    ("priorities.py", "-row.weight,  # PROVISIONAL: see open-questions Q23"),
    ("priorities.py", "row.order,  # PROVISIONAL: see open-questions Q19"),
    ("priorities.py", "PRIORITY_COUNT = 5  # PROVISIONAL: see open-questions Q21"),
    ("weights.py", "# PROVISIONAL: see open-questions Q22\nWEIGHT_LIMITS = WeightLimits("),
    ("categories.py", "# PROVISIONAL: see open-questions Q18 (category IQ shows 1 decimal)"),
    ("targets.py", "# PROVISIONAL: see open-questions Q8\ndef readiness_targets("),
    ("targets.py", "# PROVISIONAL: see open-questions Q8\ndef iq_targets("),
    ("vfm.py", "# PROVISIONAL: see open-questions Q18 (VfM divides by the rounded IQ)\ndef vfm("),
]

EXPECTED_SERVICE_MARKERS = [
    (
        "services/readiness.py",
        "# PROVISIONAL: see open-questions Q6 (one assessment type, every question required)\n"
        "    if not scored.complete",
    ),
    (
        "services/readiness.py",
        "# PROVISIONAL: see open-questions Q23 (weights order the idea list only, not this one)\n"
        "    ranked = priorities.readiness_priorities(",
    ),
]

# Decided on 2026-10-08 (Amy): these rules are CONFIRMED and must carry no PROVISIONAL marker.
DECIDED_QUESTIONS = [2, 7, 9, 20]

_MARKER = re.compile(r"PROVISIONAL: see open-questions Q(\d+)\b")


def _markers(sources: Iterable[tuple[str, str]]) -> set[tuple[str, int]]:
    """(file, question number) of every marker in the given (file, text) pairs."""
    return {(name, int(m.group(1))) for name, text in sources for m in _MARKER.finditer(text)}


@pytest.mark.parametrize(("name", "marker"), EXPECTED_MARKERS)
def test_provisional_marker_present(name: str, marker: str) -> None:
    assert marker in SOURCES[name]


@pytest.mark.parametrize(("name", "marker"), EXPECTED_SERVICE_MARKERS)
def test_service_provisional_marker_present(name: str, marker: str) -> None:
    assert marker in SERVICE_SOURCES[name]


@pytest.mark.parametrize("number", DECIDED_QUESTIONS)
def test_no_marker_for_a_decided_question(number: int) -> None:
    pattern = re.compile(rf"PROVISIONAL: see open-questions Q{number}\b")
    found = [name for name, source in (SOURCES | SERVICE_SOURCES).items() if pattern.search(source)]
    assert not found, f"Q{number} is decided but still marked PROVISIONAL in {found}"


def test_marker_set_is_exactly_the_expected_one() -> None:
    """Every PROVISIONAL marker in app/scoring is listed above; none is stale or unlisted."""
    assert _markers(SOURCES.items()) == _markers(EXPECTED_MARKERS)


def test_service_marker_set_is_exactly_the_expected_one() -> None:
    """The same for the readiness service: its pending rules are marked, and only those."""
    assert _markers(SERVICE_SOURCES.items()) == _markers(EXPECTED_SERVICE_MARKERS)


def test_every_provisional_marker_names_a_question() -> None:
    for name, source in SOURCES.items():
        for line in source.splitlines():
            if "PROVISIONAL" in line and line.lstrip().startswith("#"):
                assert re.search(r"# PROVISIONAL: see open-questions Q\d+\b", line), (name, line)


def test_scoring_source_has_no_assert_or_print() -> None:
    for name, source in SOURCES.items():
        tree = ast.parse(source)
        assert not any(isinstance(n, ast.Assert) for n in ast.walk(tree)), name
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        assert not any(isinstance(c.func, ast.Name) and c.func.id == "print" for c in calls), name
