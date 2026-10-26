"""The versioned question bank, loaded once from ``docs/methodology/dimensions.yml``.

Implements spec section 1 (12 dimensions in book order, 3 categories), 2.1 (5 questions
per dimension, answers 1 to 5), 2.4 (readiness bands), 3.1 (IQ levels) and 9 (versioning).

Nothing in ``app/scoring`` hardcodes dimension keys, names, bands or levels. They all come
from the ``QuestionSet`` built here.
"""

import os
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from types import MappingProxyType

import yaml

from app.scoring.errors import ScoringError, describe

QUESTION_SET_PATH_ENV = "INNO_QUESTION_SET_PATH"
DEFAULT_QUESTION_SET_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "methodology" / "dimensions.yml"
)

# Shape rules from the spec, checked against the file (spec 1, 2.1, 3.1).
_SPEC_DIMENSION_COUNT = 12
_SPEC_QUESTIONS_PER_DIMENSION = 5
_SPEC_READINESS_SCALE = (1, 5)
_SPEC_IQ_SCALE = (1, 10)


@dataclass(frozen=True, slots=True)
class Question:
    """One readiness question (spec 2.1)."""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class Category:
    """One of the innovation categories (spec 1)."""

    key: str
    name: str
    order: int


@dataclass(frozen=True, slots=True)
class Dimension:
    """One dimension with its questions, fixed next-step text and sub-aspects (spec 1, 8)."""

    key: str
    name: str
    order: int
    category: str
    description: str
    questions: tuple[Question, ...]
    next_steps: str
    sub_aspects: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReadinessBand:
    """A readiness band on the total, inclusive range (spec 2.4)."""

    key: str
    name: str
    min: int
    max: int
    text: str


@dataclass(frozen=True, slots=True)
class IqLevel:
    """An IQ level on one dimension score, inclusive range (spec 3.1)."""

    key: str
    name: str
    min: int
    max: int
    text: str


@dataclass(frozen=True, slots=True)
class Scale:
    """An integer answer or score scale with optional labels."""

    min: int
    max: int
    labels: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True)
class QuestionSet:
    """The validated, immutable question bank of one ``question_set_version`` (spec 1, 9)."""

    version: int
    categories: tuple[Category, ...]
    dimensions: tuple[Dimension, ...]
    readiness_scale: Scale
    readiness_bands: tuple[ReadinessBand, ...]
    iq_scale: Scale
    iq_levels: tuple[IqLevel, ...]
    _by_key: Mapping[str, Dimension] = field(init=False, repr=False, compare=False)
    _by_question: Mapping[str, Dimension] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        by_key = {d.key: d for d in self.dimensions}
        by_question = {q.id: d for d in self.dimensions for q in d.questions}
        object.__setattr__(self, "_by_key", MappingProxyType(by_key))
        object.__setattr__(self, "_by_question", MappingProxyType(by_question))

    @property
    def dimension_keys(self) -> tuple[str, ...]:
        """Dimension keys in book order."""
        return tuple(d.key for d in self.dimensions)

    def dimension(self, key: str) -> Dimension:
        """The dimension with ``key``; ScoringError if unknown."""
        try:
            return self._by_key[key]
        except (KeyError, TypeError):
            raise ScoringError(f"Unknown dimension key: {describe(key)}") from None

    def question_ids(self, key: str) -> tuple[str, ...]:
        """Question ids of one dimension, in order."""
        return tuple(q.id for q in self.dimension(key).questions)

    def all_question_ids(self) -> tuple[str, ...]:
        """All question ids, dimensions in book order."""
        return tuple(q.id for d in self.dimensions for q in d.questions)

    def dimension_of_question(self, question_id: str) -> Dimension:
        """The dimension a question belongs to; ScoringError if unknown."""
        try:
            return self._by_question[question_id]
        except (KeyError, TypeError):
            raise ScoringError(f"Unknown question id: {describe(question_id)}") from None

    def category(self, key: str) -> Category:
        """The category with ``key``; ScoringError if unknown."""
        for category in self.categories:
            if category.key == key:
                return category
        raise ScoringError(f"Unknown category key: {describe(key)}")

    def dimensions_in_category(self, key: str) -> tuple[Dimension, ...]:
        """Dimensions of one category, in book order."""
        self.category(key)
        return tuple(d for d in self.dimensions if d.category == key)

    @property
    def questions_per_dimension(self) -> int:
        """Questions per dimension (all dimensions have the same count)."""
        return len(self.dimensions[0].questions)

    @property
    def dimension_min(self) -> int:
        """Lowest readiness dimension score, derived (spec 2.2: 5)."""
        return self.questions_per_dimension * self.readiness_scale.min

    @property
    def dimension_max(self) -> int:
        """Highest readiness dimension score, derived (spec 2.2: 25)."""
        return self.questions_per_dimension * self.readiness_scale.max

    @property
    def total_min(self) -> int:
        """Lowest readiness total, derived (spec 2.3: 60)."""
        return len(self.dimensions) * self.dimension_min

    @property
    def total_max(self) -> int:
        """Highest readiness total, derived (spec 2.3: 300)."""
        return len(self.dimensions) * self.dimension_max


# --- YAML loading -------------------------------------------------------------------------


type _SafeLoader = yaml.SafeLoader | yaml.CSafeLoader


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of keeping the last one."""


_MERGE_TAG = "tag:yaml.org,2002:merge"


def _construct_unique_mapping(loader: _SafeLoader, node: yaml.MappingNode) -> object:
    for key_node, _value in node.value:
        if key_node.tag == _MERGE_TAG:
            raise ScoringError(f"YAML merge keys (<<) are not allowed, at {key_node.start_mark}")
    seen: set[Hashable] = set()
    for key_node, _value in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, Hashable):
            raise ScoringError(f"Unhashable mapping key at {key_node.start_mark}")
        if key in seen:
            raise ScoringError(f"Duplicate key {describe(key)} at {key_node.start_mark}")
        seen.add(key)
    return loader.construct_mapping(node)


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)

# The first loader is the one used: the libyaml parser (about 10x faster, same safe
# constructor) when PyYAML was built with it, otherwise the pure-Python SafeLoader subclass.
_LOADERS: tuple[type[_SafeLoader], ...] = (_UniqueKeyLoader,)
if yaml.__with_libyaml__:

    class _CUniqueKeyLoader(yaml.CSafeLoader):
        """C-parser twin of _UniqueKeyLoader; same safe constructor, same duplicate check."""

    _CUniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _construct_unique_mapping,
    )
    _LOADERS = (_CUniqueKeyLoader, _UniqueKeyLoader)


def default_question_set_path() -> Path:
    """The file to load: ``$INNO_QUESTION_SET_PATH`` if set, else the repo dimensions.yml."""
    override = os.environ.get(QUESTION_SET_PATH_ENV)
    return Path(override).resolve() if override else DEFAULT_QUESTION_SET_PATH


def load_question_set(path: Path | str | None = None) -> QuestionSet:
    """Load and validate a question set file (spec 1, 2.1, 2.4, 3.1).

    Raises ScoringError if the file is missing, is not valid YAML, has duplicate keys or
    breaks any shape rule.
    """
    source = Path(path).resolve() if path is not None else default_question_set_path()
    try:
        raw_text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScoringError(f"Cannot read question set file {source}: {exc}") from exc
    data = _parse_yaml(raw_text, str(source), _LOADERS[0])
    try:
        return _build(data)
    except ScoringError as exc:
        raise ScoringError(f"Invalid question set {source}: {exc}") from exc


def _parse_yaml(text: str, source: str, loader: type[_SafeLoader]) -> object:
    """Parse with a safe, duplicate-rejecting loader; YAML errors become ScoringError."""
    try:
        return yaml.load(text, Loader=loader)  # noqa: S506 (safe loaders only)
    except yaml.YAMLError as exc:
        raise ScoringError(f"Invalid YAML in {source}: {exc}") from exc
    except ScoringError as exc:
        raise ScoringError(f"Invalid YAML in {source}: {exc}") from exc


# --- Validation ---------------------------------------------------------------------------


def _mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(k, str) for k in value):
        raise ScoringError(f"{where} must be a mapping with text keys")
    return value


def _sequence(value: object, where: str) -> Sequence[object]:
    if not isinstance(value, list) or not value:
        raise ScoringError(f"{where} must be a non-empty list")
    return value


def _text(data: Mapping[str, object], name: str, where: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ScoringError(f"{where}.{name} must be a non-empty string")
    return value


def _integer(data: Mapping[str, object], name: str, where: str) -> int:
    value = data.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ScoringError(f"{where}.{name} must be an integer")
    return value


def _scale(data: Mapping[str, object], name: str, expected: tuple[int, int]) -> Scale:
    raw = _mapping(data.get(name), name)
    low, high = _integer(raw, "min", name), _integer(raw, "max", name)
    if (low, high) != expected:
        raise ScoringError(f"{name} must be {expected[0]} to {expected[1]}, got {low} to {high}")
    labels_raw = raw.get("labels", {})
    if not isinstance(labels_raw, Mapping):
        raise ScoringError(f"{name}.labels must be a mapping")
    labels: list[tuple[int, str]] = []
    for value, label in labels_raw.items():
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise ScoringError(f"{name}.labels key {describe(value)} is not on the scale")
        if not isinstance(label, str) or not label.strip():
            raise ScoringError(f"{name}.labels[{value}] must be a non-empty string")
        labels.append((value, label))
    return Scale(min=low, max=high, labels=tuple(sorted(labels)))


def _ranges[T: (ReadinessBand, IqLevel)](
    raw_list: object, name: str, kind: type[T], low: int, high: int, *, open_bottom: bool
) -> tuple[T, ...]:
    """Parse inclusive ranges and check they cover low..high with no overlap or gap.

    With ``open_bottom`` the lowest range may start below ``low`` (but not below 0).
    """
    items: list[T] = []
    for i, entry in enumerate(_sequence(raw_list, name)):
        where = f"{name}[{i}]"
        raw = _mapping(entry, where)
        item = kind(
            key=_text(raw, "key", where),
            name=_text(raw, "name", where),
            min=_integer(raw, "min", where),
            max=_integer(raw, "max", where),
            text=_text(raw, "text", where),
        )
        if item.min > item.max:
            raise ScoringError(f"{where} has min {item.min} above max {item.max}")
        items.append(item)
    _unique([i.key for i in items], f"{name} key")
    _unique([i.name for i in items], f"{name} name")
    ordered = sorted(items, key=lambda i: i.min)
    bottom = ordered[0].min
    if open_bottom:
        if not 0 <= bottom <= low:
            raise ScoringError(f"{name} must start between 0 and {low}, starts at {bottom}")
    elif bottom != low:
        raise ScoringError(f"{name} must start exactly at {low}, starts at {bottom}")
    for below, above in pairwise(ordered):
        if above.min <= below.max:
            raise ScoringError(f"{name} {below.key} and {above.key} overlap")
        if above.min != below.max + 1:
            raise ScoringError(f"{name} has a gap between {below.key} and {above.key}")
    if ordered[-1].max != high:
        raise ScoringError(f"{name} must end exactly at {high}, ends at {ordered[-1].max}")
    return tuple(ordered)


def _unique(values: Sequence[str], what: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ScoringError(f"Duplicate {what}: {describe(value)}")
        seen.add(value)


def _orders_are_1_to_n(orders: Sequence[int], what: str) -> None:
    if sorted(orders) != list(range(1, len(orders) + 1)):
        raise ScoringError(f"{what} order values must be 1 to {len(orders)}, got {orders}")


def _build_categories(raw_list: object) -> tuple[Category, ...]:
    categories = []
    for i, entry in enumerate(_sequence(raw_list, "categories")):
        where = f"categories[{i}]"
        raw = _mapping(entry, where)
        categories.append(
            Category(
                key=_text(raw, "key", where),
                name=_text(raw, "name", where),
                order=_integer(raw, "order", where),
            )
        )
    _unique([c.key for c in categories], "category key")
    _orders_are_1_to_n([c.order for c in categories], "Category")
    return tuple(sorted(categories, key=lambda c: c.order))


def _build_dimension(entry: object, i: int, category_keys: set[str]) -> Dimension:
    where = f"dimensions[{i}]"
    raw = _mapping(entry, where)
    key = _text(raw, "key", where)
    category = _text(raw, "category", where)
    if category not in category_keys:
        raise ScoringError(f"{where} ({key}) has unknown category {describe(category)}")
    questions = []
    for j, q_entry in enumerate(_sequence(raw.get("readiness_questions"), f"{key}.questions")):
        q_where = f"{key}.readiness_questions[{j}]"
        q_raw = _mapping(q_entry, q_where)
        questions.append(
            Question(id=_text(q_raw, "id", q_where), text=_text(q_raw, "text", q_where))
        )
    if len(questions) != _SPEC_QUESTIONS_PER_DIMENSION:
        raise ScoringError(
            f"Dimension {key} must have exactly {_SPEC_QUESTIONS_PER_DIMENSION} questions, "
            f"has {len(questions)}"
        )
    sub_aspects = _sequence(raw.get("sub_aspects"), f"{key}.sub_aspects")
    for aspect in sub_aspects:
        if not isinstance(aspect, str) or not aspect.strip():
            raise ScoringError(f"{key}.sub_aspects must contain only non-empty strings")
    return Dimension(
        key=key,
        name=_text(raw, "name", where),
        order=_integer(raw, "order", where),
        category=category,
        description=_text(raw, "description", where),
        questions=tuple(questions),
        next_steps=_text(raw, "next_steps", where),
        sub_aspects=tuple(str(a) for a in sub_aspects),
    )


def _build(data: object) -> QuestionSet:
    root = _mapping(data, "question set")
    version = _integer(root, "question_set_version", "question set")
    if version < 1:
        raise ScoringError(f"question_set_version must be 1 or more, got {describe(version)}")

    categories = _build_categories(root.get("categories"))
    category_keys = {c.key for c in categories}
    raw_dimensions = _sequence(root.get("dimensions"), "dimensions")
    dimensions = [_build_dimension(d, i, category_keys) for i, d in enumerate(raw_dimensions)]
    if len(dimensions) != _SPEC_DIMENSION_COUNT:
        raise ScoringError(
            f"Expected exactly {_SPEC_DIMENSION_COUNT} dimensions, found {len(dimensions)}"
        )
    _unique([d.key for d in dimensions], "dimension key")
    _unique([d.name for d in dimensions], "dimension name")
    _unique([q.id for d in dimensions for q in d.questions], "question id")
    _orders_are_1_to_n([d.order for d in dimensions], "Dimension")
    empty = [c.key for c in categories if not any(d.category == c.key for d in dimensions)]
    if empty:
        raise ScoringError(f"Categories without any dimension: {empty}")

    readiness_scale = _scale(root, "readiness_scale", _SPEC_READINESS_SCALE)
    iq_scale = _scale(root, "iq_scale", _SPEC_IQ_SCALE)
    total_min = len(dimensions) * _SPEC_QUESTIONS_PER_DIMENSION * readiness_scale.min
    total_max = len(dimensions) * _SPEC_QUESTIONS_PER_DIMENSION * readiness_scale.max
    bands = _ranges(
        root.get("readiness_bands"),
        "readiness_bands",
        ReadinessBand,
        total_min,
        total_max,
        open_bottom=True,
    )
    levels = _ranges(
        root.get("iq_levels"), "iq_levels", IqLevel, iq_scale.min, iq_scale.max, open_bottom=False
    )
    return QuestionSet(
        version=version,
        categories=categories,
        dimensions=tuple(sorted(dimensions, key=lambda d: d.order)),
        readiness_scale=readiness_scale,
        readiness_bands=bands,
        iq_scale=iq_scale,
        iq_levels=levels,
    )


QUESTION_SET: QuestionSet = load_question_set()


def _older_versions(source: Path, latest: QuestionSet) -> dict[int, QuestionSet]:
    """The ``<stem>.v<N>.yml`` siblings of ``source``, each checked against its name."""
    older: dict[int, QuestionSet] = {}
    for sibling in sorted(source.parent.glob(f"{source.stem}.v*{source.suffix}")):
        tag = sibling.name[len(source.stem) + 2 : -len(source.suffix)]
        if not tag.isdigit():
            continue
        loaded = load_question_set(sibling)
        if loaded.version != int(tag):
            raise ScoringError(
                f"Question set {sibling} is named v{tag} but declares version {loaded.version}"
            )
        if loaded.version >= latest.version:
            raise ScoringError(
                f"Question set {sibling} (version {loaded.version}) must be older than "
                f"{source} (version {latest.version})"
            )
        older[loaded.version] = loaded
    return older


def load_registry(path: Path | str | None = None) -> Mapping[int, QuestionSet]:
    """Every question set version known from one place (spec 9).

    ``path`` (default: ``default_question_set_path()``) is the authoritative latest version.
    Older versions live beside it as ``<stem>.v<N>.yml`` and are loaded too, so an
    assessment started on an earlier version can still be read and scored after a bump.
    Each sibling must declare the version in its name and be older than the main file.
    """
    source = Path(path).resolve() if path is not None else default_question_set_path()
    latest = load_question_set(source)
    return MappingProxyType({latest.version: latest, **_older_versions(source, latest)})


_REGISTRY: Mapping[int, QuestionSet] = MappingProxyType(
    {
        QUESTION_SET.version: QUESTION_SET,
        **_older_versions(default_question_set_path(), QUESTION_SET),
    }
)


def question_set_for(version: int) -> QuestionSet:
    """The question set of a stored ``question_set_version`` (spec 9).

    Known versions are the main file and its ``.v<N>`` siblings (``load_registry``).
    Unknown or non-integer versions raise ScoringError.
    """
    if not isinstance(version, int) or isinstance(version, bool):
        raise ScoringError(f"question_set_version must be an integer, got {describe(version)}")
    try:
        return _REGISTRY[version]
    except KeyError:
        raise ScoringError(f"Unknown question_set_version: {describe(version)}") from None
