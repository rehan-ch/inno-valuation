"""Question set loading and validation (spec 1, 2.1, 2.4, 3.1, 9)."""

import dataclasses
import os
import re
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

import app.scoring.question_set as qs_module
from app.scoring.errors import ScoringError
from app.scoring.question_set import (
    DEFAULT_QUESTION_SET_PATH,
    QUESTION_SET,
    QUESTION_SET_PATH_ENV,
    default_question_set_path,
    load_question_set,
    question_set_for,
)
from tests.scoring.support import raw_question_set, write_variant

SPEC = DEFAULT_QUESTION_SET_PATH.parents[0] / "scoring-spec.md"
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _spec_section(number: str) -> str:
    text = SPEC.read_text(encoding="utf-8")
    match = re.search(rf"^##+ {re.escape(number)}\s.*?(?=^##+ )", text, re.S | re.M)
    assert match, f"spec section {number} not found"
    return match.group(0)


# --- the real file -----------------------------------------------------------------------


def test_real_file_loads_version_1_with_12_dimensions_of_5_questions() -> None:
    assert QUESTION_SET.version == 1
    assert len(QUESTION_SET.dimensions) == 12
    assert all(len(d.questions) == 5 for d in QUESTION_SET.dimensions)
    assert len(set(QUESTION_SET.all_question_ids())) == 60


def test_dimensions_match_spec_section_1_table_in_book_order() -> None:
    rows = re.findall(
        r"^\| (\d+) \| ([^|]+?) \| `([a-z_]+)` \| ([^|]+?) \|$", _spec_section("1."), re.M
    )
    assert len(rows) == 12
    for dimension, (order, name, key, category) in zip(QUESTION_SET.dimensions, rows, strict=True):
        assert (dimension.order, dimension.name, dimension.key) == (int(order), name, key)
        assert QUESTION_SET.category(dimension.category).name.startswith(category)


def test_dimension_order_follows_the_file_and_runs_1_to_12() -> None:
    raw_keys = [d["key"] for d in raw_question_set()["dimensions"]]
    assert list(QUESTION_SET.dimension_keys) == raw_keys
    assert [d.order for d in QUESTION_SET.dimensions] == list(range(1, 13))


def test_readiness_bands_match_spec_section_2_4_exactly() -> None:
    rows = re.findall(r"^\| ([A-Z][^|]+?) \| ([^|]+?) \| ([^|]+?) \|$", _spec_section("2.4"), re.M)
    spec = {name: text for name, _range, text in rows if name != "Band"}
    assert {b.name: b.text for b in QUESTION_SET.readiness_bands} == spec


def test_iq_levels_match_spec_section_3_1() -> None:
    rows = re.findall(r"^\s+- (\d+) to (\d+): (.+)$", _spec_section("3.1"), re.M)
    assert [(lvl.min, lvl.max, lvl.name) for lvl in QUESTION_SET.iq_levels] == [
        (int(a), int(b), name) for a, b, name in rows
    ]


def test_scales_and_derived_ranges() -> None:
    qs = QUESTION_SET
    assert (qs.readiness_scale.min, qs.readiness_scale.max) == (1, 5)
    assert (qs.iq_scale.min, qs.iq_scale.max) == (1, 10)
    assert (qs.dimension_min, qs.dimension_max) == (5, 25)
    assert (qs.total_min, qs.total_max) == (60, 300)
    assert dict(qs.readiness_scale.labels) == {1: "Strongly Disagree", 5: "Strongly Agree"}


def test_categories_in_order_with_their_dimensions() -> None:
    sizes = [len(QUESTION_SET.dimensions_in_category(c.key)) for c in QUESTION_SET.categories]
    assert [c.order for c in QUESTION_SET.categories] == [1, 2, 3]
    assert sizes == [5, 2, 5]
    every = [d for c in QUESTION_SET.categories for d in QUESTION_SET.dimensions_in_category(c.key)]
    assert tuple(every) == QUESTION_SET.dimensions


def test_lookup_helpers() -> None:
    first = QUESTION_SET.dimensions[0]
    assert QUESTION_SET.dimension(first.key) is first
    assert QUESTION_SET.question_ids(first.key) == tuple(q.id for q in first.questions)
    assert QUESTION_SET.dimension_of_question(first.questions[3].id) is first
    assert QUESTION_SET.all_question_ids()[:5] == QUESTION_SET.question_ids(first.key)
    assert first.sub_aspects
    assert first.next_steps
    assert first.description


@pytest.mark.parametrize(
    "call",
    [
        lambda: QUESTION_SET.dimension("nope"),
        lambda: QUESTION_SET.question_ids("nope"),
        lambda: QUESTION_SET.dimension_of_question("nope_1"),
        lambda: QUESTION_SET.dimensions_in_category("nope"),
        lambda: QUESTION_SET.category("nope"),
    ],
)
def test_lookup_helpers_reject_unknown_keys(call: Any) -> None:
    with pytest.raises(ScoringError, match="Unknown"):
        call()


def test_internal_lookup_maps_are_read_only() -> None:
    by_key = QUESTION_SET._by_key
    assert isinstance(by_key, MappingProxyType)
    assert isinstance(QUESTION_SET._by_question, MappingProxyType)
    with pytest.raises(TypeError):
        by_key["x"] = QUESTION_SET.dimensions[0]  # type: ignore[index]


def test_bands_and_levels_are_sorted_ascending() -> None:
    assert [b.min for b in QUESTION_SET.readiness_bands] == sorted(
        b.min for b in QUESTION_SET.readiness_bands
    )
    assert QUESTION_SET.readiness_bands[0].min == 0
    assert QUESTION_SET.readiness_bands[-1].max == 300
    assert [lvl.min for lvl in QUESTION_SET.iq_levels] == [1, 4, 7]


def test_shuffled_bands_and_levels_load_sorted(tmp_path: Path) -> None:
    def shuffle(d: dict[str, Any]) -> None:
        bands = d["readiness_bands"]
        d["readiness_bands"] = [bands[2], bands[0], bands[3], bands[1]]
        levels = d["iq_levels"]
        d["iq_levels"] = [levels[2], levels[0], levels[1]]

    loaded = load_question_set(write_variant(tmp_path, shuffle))
    assert loaded.readiness_bands == QUESTION_SET.readiness_bands
    assert loaded.iq_levels == QUESTION_SET.iq_levels


def test_question_set_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        QUESTION_SET.version = 2  # type: ignore[misc]
    assert isinstance(QUESTION_SET.dimensions, tuple)
    assert isinstance(QUESTION_SET.dimensions[0].questions, tuple)


# --- registry and path -------------------------------------------------------------------


def test_question_set_for_known_version() -> None:
    assert question_set_for(1) is QUESTION_SET


@pytest.mark.parametrize("version", [0, 2, -1, "1", 1.0, True, None])
def test_question_set_for_rejects_unknown_or_non_int(version: Any) -> None:
    with pytest.raises(ScoringError, match="question_set_version"):
        question_set_for(version)


def test_default_path_is_the_repo_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(QUESTION_SET_PATH_ENV, raising=False)
    assert default_question_set_path() == DEFAULT_QUESTION_SET_PATH
    assert DEFAULT_QUESTION_SET_PATH.is_file()


def test_env_var_overrides_the_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = write_variant(tmp_path, lambda d: d.update(question_set_version=7))
    monkeypatch.setenv(QUESTION_SET_PATH_ENV, str(path))
    assert default_question_set_path() == path
    assert load_question_set().version == 7


def test_env_var_path_is_resolved_to_absolute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = write_variant(tmp_path, lambda d: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(QUESTION_SET_PATH_ENV, f"./{path.name}")
    resolved = default_question_set_path()
    assert resolved.is_absolute()
    assert resolved == path.resolve()


def test_load_errors_name_the_resolved_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good = write_variant(tmp_path, lambda d: d.update(question_set_version=0))
    dup = tmp_path / "dup.yml"
    dup.write_text("a: 1\na: 2\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ScoringError, match=re.escape(str(good.resolve()))):
        load_question_set(good.name)
    with pytest.raises(ScoringError, match=re.escape(str(dup.resolve()))) as info:
        load_question_set("dup.yml")
    assert "Duplicate key 'a'" in str(info.value)
    monkeypatch.setenv(QUESTION_SET_PATH_ENV, "missing.yml")
    with pytest.raises(ScoringError, match=re.escape(str((tmp_path / "missing.yml").resolve()))):
        load_question_set()


def test_env_var_is_used_at_import(tmp_path: Path) -> None:
    path = write_variant(tmp_path, lambda d: d.update(question_set_version=3))
    env = {**os.environ, QUESTION_SET_PATH_ENV: str(path)}
    code = (
        "from app.scoring.question_set import QUESTION_SET, question_set_for\n"
        "print(QUESTION_SET.version, question_set_for(3).version)"
    )
    out = subprocess.run(  # noqa: S603 (fixed interpreter and code)
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.split() == ["3", "3"]


# --- invalid files -----------------------------------------------------------------------


def _dims(d: dict[str, Any]) -> list[dict[str, Any]]:
    dims = d["dimensions"]
    assert isinstance(dims, list)
    return dims


def _extra_dimension(d: dict[str, Any]) -> None:
    extra = {**_dims(d)[0], "key": "extra", "name": "Extra", "order": 13}
    extra["readiness_questions"] = [{"id": f"extra_{i}", "text": "Q?"} for i in range(1, 6)]
    _dims(d).append(extra)


def _band(d: dict[str, Any], key: str) -> dict[str, Any]:
    return next(b for b in d["readiness_bands"] if b["key"] == key)


def _level(d: dict[str, Any], key: str) -> dict[str, Any]:
    return next(b for b in d["iq_levels"] if b["key"] == key)


INVALID_VARIANTS: list[tuple[str, Any, str]] = [
    ("11 dimensions", lambda d: _dims(d).pop(), "exactly 12 dimensions"),
    ("13 dimensions", _extra_dimension, "exactly 12 dimensions"),
    ("4 questions", lambda d: _dims(d)[0]["readiness_questions"].pop(), "exactly 5 questions"),
    (
        "6 questions",
        lambda d: _dims(d)[0]["readiness_questions"].append({"id": "x_6", "text": "Q?"}),
        "exactly 5 questions",
    ),
    ("no questions", lambda d: _dims(d)[0].update(readiness_questions=[]), "non-empty list"),
    ("duplicate dimension key", lambda d: _dims(d)[1].update(key=_dims(d)[0]["key"]), "Duplicate"),
    (
        "duplicate dimension name",
        lambda d: _dims(d)[1].update(name=_dims(d)[0]["name"]),
        "Duplicate dimension name",
    ),
    (
        "duplicate question id",
        lambda d: _dims(d)[1]["readiness_questions"][0].update(
            id=_dims(d)[0]["readiness_questions"][0]["id"]
        ),
        "Duplicate question id",
    ),
    ("unknown category", lambda d: _dims(d)[0].update(category="nope"), "unknown category"),
    (
        "category without dimensions",
        lambda d: d["categories"].append({"key": "empty", "name": "Empty", "order": 4}),
        "without any dimension",
    ),
    (
        "duplicate category key",
        lambda d: d["categories"][1].update(key=d["categories"][0]["key"]),
        "Duplicate category key",
    ),
    ("category order gap", lambda d: d["categories"][2].update(order=5), "Category order"),
    ("dimension order 13", lambda d: _dims(d)[11].update(order=13), "Dimension order"),
    ("dimension order repeated", lambda d: _dims(d)[11].update(order=1), "Dimension order"),
    ("dimension order text", lambda d: _dims(d)[0].update(order="1"), "must be an integer"),
    ("empty sub_aspects", lambda d: _dims(d)[0].update(sub_aspects=[]), "non-empty list"),
    ("blank sub_aspect", lambda d: _dims(d)[0]["sub_aspects"].append("  "), "non-empty strings"),
    ("numeric sub_aspect", lambda d: _dims(d)[0]["sub_aspects"].append(5), "non-empty strings"),
    ("missing name", lambda d: _dims(d)[0].pop("name"), "name must be a non-empty string"),
    (
        "blank question text",
        lambda d: _dims(d)[0]["readiness_questions"][0].update(text=""),
        "text",
    ),
    ("missing next_steps", lambda d: _dims(d)[0].pop("next_steps"), "next_steps"),
    ("version 0", lambda d: d.update(question_set_version=0), "1 or more"),
    ("version text", lambda d: d.update(question_set_version="1"), "must be an integer"),
    ("version bool", lambda d: d.update(question_set_version=True), "must be an integer"),
    ("band overlap", lambda d: _band(d, "building_blocks").update(max=250), "overlap"),
    ("band gap", lambda d: _band(d, "building_blocks").update(min=176), "gap"),
    ("bands end at 299", lambda d: _band(d, "innovation_champion").update(max=299), "end exactly"),
    ("bands end at 301", lambda d: _band(d, "innovation_champion").update(max=301), "end exactly"),
    ("bottom band below 0", lambda d: _band(d, "beginner").update(min=-1), "start between"),
    ("bottom band above 60", lambda d: _band(d, "beginner").update(min=61), "start between"),
    ("band min above max", lambda d: _band(d, "emerging_innovator").update(max=99), "above max"),
    (
        "duplicate band key",
        lambda d: _band(d, "beginner").update(key="building_blocks"),
        "Duplicate readiness_bands key",
    ),
    ("band without text", lambda d: _band(d, "beginner").pop("text"), "text"),
    ("no bands", lambda d: d.update(readiness_bands=[]), "non-empty list"),
    ("levels start at 2", lambda d: _level(d, "continuous_improvement").update(min=2), "start"),
    ("levels start at 0", lambda d: _level(d, "continuous_improvement").update(min=0), "start"),
    ("levels end at 9", lambda d: _level(d, "invention").update(max=9), "end exactly"),
    ("levels end at 11", lambda d: _level(d, "invention").update(max=11), "end exactly"),
    ("level overlap", lambda d: _level(d, "innovation").update(max=7), "overlap"),
    ("level gap", lambda d: _level(d, "innovation").update(max=5), "gap"),
    ("readiness scale 0 to 5", lambda d: d["readiness_scale"].update(min=0), "readiness_scale"),
    ("iq scale 1 to 9", lambda d: d["iq_scale"].update(max=9), "iq_scale"),
    ("label off scale", lambda d: d["readiness_scale"]["labels"].update({6: "x"}), "not on"),
]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [pytest.param(m, msg, id=name) for name, m, msg in INVALID_VARIANTS],
)
def test_invalid_question_set_is_rejected(tmp_path: Path, mutate: Any, message: str) -> None:
    path = write_variant(tmp_path, mutate)
    with pytest.raises(ScoringError, match=message):
        load_question_set(path)


def test_unmodified_copy_loads(tmp_path: Path) -> None:
    path = write_variant(tmp_path, lambda d: None)
    assert load_question_set(path) == QUESTION_SET


def test_reordered_file_is_sorted_into_book_order(tmp_path: Path) -> None:
    path = write_variant(tmp_path, lambda d: d["dimensions"].reverse())
    assert load_question_set(path).dimension_keys == QUESTION_SET.dimension_keys


@pytest.mark.parametrize(
    ("text", "message"),
    [
        pytest.param("- just\n- a list\n", "mapping", id="root is a list"),
        pytest.param("a: [unclosed\n", "Invalid YAML", id="syntax error"),
        pytest.param("", "mapping", id="empty file"),
        pytest.param("a: 1\nb: 2\na: 3\n", "Duplicate key 'a'", id="duplicate top-level key"),
        pytest.param("a:\n  x: 1\n  x: 2\n", "Duplicate key 'x'", id="duplicate nested key"),
        pytest.param("? [1, 2]\n: x\n", "Unhashable", id="unhashable key"),
        pytest.param("base: &b {x: 1}\nchild:\n  <<: *b\n  y: 2\n", "merge keys", id="merge key"),
        pytest.param(
            "base: &b {x: 1}\nchild:\n  <<: *b\n  x: 2\n", "merge keys", id="merge override"
        ),
        pytest.param("a: !!python/object:os.system x\n", "Invalid YAML", id="unsafe tag"),
    ],
)
def test_bad_yaml_text_is_rejected(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "bad.yml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ScoringError, match=message):
        load_question_set(path)


def test_duplicate_key_inside_the_real_file_is_rejected(tmp_path: Path) -> None:
    original = DEFAULT_QUESTION_SET_PATH.read_text(encoding="utf-8")
    first_key_line = "  - key: customer_journey\n"
    assert first_key_line in original
    path = tmp_path / "dup.yml"
    path.write_text(
        original.replace(first_key_line, first_key_line + "    key: brand_magnetism\n", 1),
        encoding="utf-8",
    )
    with pytest.raises(ScoringError, match="Duplicate key 'key'"):
        load_question_set(path)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ScoringError, match="Cannot read"):
        load_question_set(tmp_path / "absent.yml")


@pytest.mark.parametrize("loader", qs_module._LOADERS, ids=lambda cls: cls.__name__)
def test_every_loader_is_safe_and_rejects_duplicate_keys(loader: Any) -> None:
    with pytest.raises(ScoringError, match="Duplicate key 'a'"):
        qs_module._parse_yaml("a: 1\na: 2\n", "inline", loader)
    with pytest.raises(ScoringError, match="Invalid YAML"):
        qs_module._parse_yaml("a: !!python/name:os.system\n", "inline", loader)
    with pytest.raises(ScoringError, match="merge keys"):
        qs_module._parse_yaml("b: &b {x: 1}\nc: {<<: *b}\n", "inline", loader)
    assert qs_module._parse_yaml("a: {b: 1}\n", "inline", loader) == {"a": {"b": 1}}
