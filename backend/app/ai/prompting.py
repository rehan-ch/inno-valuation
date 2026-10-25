"""Prompt templates: one Jinja2 file per touchpoint in ``app/ai/prompts/<key>.md``.

A template has a ``system`` block and a ``user`` block, and states its version on its
first line as ``{# prompt_version: <n>``. The version is stored with every run; a test
pins each template's content to its version, so a changed prompt cannot ship without a
new version number.

Methodology text (dimension names, descriptions, questions) is passed in from the question
set, never retyped in a template. Text that people typed is passed through ``as_data``,
which wraps it in ``<data>`` tags the system prompt calls information, not instructions.
"""

import hashlib
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from jinja2 import Environment, FileSystemLoader, StrictUndefined

PROMPTS_DIR: Final = Path(__file__).resolve().parent / "prompts"

_VERSION: Final = re.compile(r"\A\{#-?\s*prompt_version:\s*(\S+)")
_DATA_NAME: Final = re.compile(r"\A[a-z][a-z0-9_]*\Z")


def as_data(name: str, text: str) -> str:
    """``text`` wrapped in ``<data name="...">`` tags. Angle brackets and ampersands inside
    are escaped, so the text can neither close the tag nor open one of its own."""
    if not _DATA_NAME.match(name):
        raise ValueError(f"Not a data block name: {name!r}")
    return f'<data name="{name}">\n{html.escape(text, quote=False)}\n</data>'


_env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    undefined=StrictUndefined,
    autoescape=False,  # noqa: S701  (prompts are plain text for a model, not HTML)
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.globals["as_data"] = as_data


@dataclass(frozen=True)
class RenderedPrompt:
    version: str
    system: str
    user: str


def _source(key: str) -> str:
    return (PROMPTS_DIR / f"{key}.md").read_text(encoding="utf-8")


def prompt_version(key: str) -> str:
    found = _VERSION.match(_source(key))
    if found is None:
        raise ValueError(f"{key}.md must start with '{{# prompt_version: <n>'.")
    return found.group(1)


def template_digest(key: str) -> str:
    """SHA-256 of the template and every shared partial (``_*.md``) it may include."""
    digest = hashlib.sha256(_source(key).encode())
    for partial in sorted(PROMPTS_DIR.glob("_*.md")):
        digest.update(partial.read_bytes())
    return digest.hexdigest()


def render(key: str, **variables: Any) -> RenderedPrompt:
    template = _env.get_template(f"{key}.md")
    context = template.new_context(variables)
    system = "".join(template.blocks["system"](context)).strip()
    user = "".join(template.blocks["user"](context)).strip()
    return RenderedPrompt(version=prompt_version(key), system=system, user=user)
