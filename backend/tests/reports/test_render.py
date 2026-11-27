"""Drawing a report from a snapshot: the wording helpers, the compass, what may be loaded,
escaping, and reports with long content or with the optional parts missing."""

import io
import re
from copy import deepcopy
from typing import Any

import pytest
from pypdf import PdfReader

from app.reports import render
from app.reports.compass import compass_svg, fill_of
from app.reports.render import gap_words, long_date, money, render_html, render_pdf, whole
from app.reports.snapshot import TEMPLATE_VERSION
from app.scoring.question_set import QUESTION_SET

DIMENSIONS = QUESTION_SET.dimensions


def _compass(*, targets: bool = True, levels: bool = False) -> dict[str, Any]:
    segments = [
        {
            "key": d.key,
            "name": d.name,
            "order": d.order,
            "category": d.category,
            "score": 15,
            "maximum": 25,
            "level": {"key": "x", "name": "Level two", "order": 2} if levels else None,
            "priority_rank": 1 if d.order == 3 else None,
            "target": 20 if targets and d.order == 1 else None,
            "gap": 5 if targets and d.order == 1 else None,
        }
        for d in DIMENSIONS
    ]
    return {
        "scale": "readiness",
        "question_set_version": 1,
        "minimum": 5,
        "maximum": 25,
        "segments": segments,
        "categories": [
            {
                "key": c.key,
                "name": c.name,
                "order": i + 1,
                "score": "75",
                "maximum": "125",
                "dimension_keys": [d.key for d in DIMENSIONS if d.category == c.key],
            }
            for i, c in enumerate(QUESTION_SET.categories)
        ],
        "levels": [],
    }


def _readiness(**result: Any) -> dict[str, Any]:
    dims = [
        {
            "key": d.key,
            "name": d.name,
            "order": d.order,
            "category": d.category,
            "score": 15,
            "maximum": 25,
        }
        for d in DIMENSIONS
    ]
    return {
        "template_version": TEMPLATE_VERSION,
        "kind": "readiness",
        "organisation": {"name": "Acme Ltd"},
        "requested_by": "Dana Okafor",
        "generated_at": "2026-11-27T10:00:00+00:00",
        "result": {
            "assessment_id": "00000000-0000-0000-0000-000000000001",
            "question_set_version": 1,
            "total": 180,
            "total_maximum": 300,
            "band": {"key": "b", "name": "Building Blocks", "text": "A strong foundation."},
            "dimensions": dims,
            "categories": [
                {"key": c.key, "name": c.name, "score": 60, "maximum": 100}
                for c in QUESTION_SET.categories
            ],
            "priorities": [
                {
                    "rank": 1,
                    "key": DIMENSIONS[2].key,
                    "name": DIMENSIONS[2].name,
                    "score": 15,
                    "maximum": 25,
                    "next_steps": DIMENSIONS[2].next_steps,
                }
            ],
            "strengths": [],
            "compass": _compass(),
            "submitted_count": 1,
            "finalised_at": "2026-11-19T09:00:00+00:00",
            **result,
        },
        "advice": None,
    }


def _text(pdf: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf))
    return " ".join(" ".join(page.extract_text() or "" for page in reader.pages).split())


def test_wording_helpers_match_the_app() -> None:
    assert gap_words(3) == "3 below target"
    assert gap_words(-2) == "2 above target"
    assert gap_words(0) == "on target"
    assert gap_words(None) == "–"  # noqa: RUF001  (the app's dash)
    assert money("50000.00", "USD") == "USD 50,000.00"
    assert money("1235", "JPY") == "JPY 1,235"
    assert money("714.29", "EUR") == "EUR 714.29"
    assert money("n/a", "USD") == "USD n/a"
    assert whole("100.0") == "100"
    assert whole("72.5") == "72.5"
    assert long_date("2026-11-19T23:30:00+00:00") == "19 November 2026"


def test_the_compass_draws_twelve_segments_and_the_targets() -> None:
    svg = str(compass_svg(_compass(), value="180", maximum="300", label="Building Blocks"))
    # A background and a filled slice per dimension, one dashed mark for the one target.
    assert svg.count('stroke="white"') == 2 * len(DIMENSIONS)
    assert svg.count("stroke-dasharray") == 1
    assert ">180<" in svg
    assert ">out of 300<" in svg


def test_the_compass_escapes_what_it_writes() -> None:
    svg = str(compass_svg(_compass(), value="<script>", maximum="300", label='"x" & y'))
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
    assert "&#34;x&#34; &amp; y" in svg


def test_levels_take_the_ramp_by_position() -> None:
    def segment(order: int) -> dict[str, Any]:
        return {"level": {"order": order}}

    assert [fill_of(segment(o), 3) for o in (1, 2, 3)] == ["#9cc9ee", "#2e86d1", "#114a7a"]
    assert fill_of({"level": None}, 3) == fill_of(segment(1), 0) == "#166eb6"


def test_user_text_is_escaped() -> None:
    snapshot = _readiness()
    snapshot["organisation"]["name"] = '<img src="https://evil.example/x.png"> Acme'
    html = render_html(snapshot)
    assert '<img src="https://evil' not in html
    assert "&lt;img src=" in html


def test_a_report_may_load_only_its_own_files() -> None:
    fetcher = render._LocalFilesOnly()
    for url in (
        "https://example.com/x.png",
        "file:///etc/passwd",
        (render.REPORTS_DIR / ".." / "core" / "settings.py").as_uri(),
        "data:text/plain,hello",
    ):
        with pytest.raises(ValueError, match="may not load"):
            fetcher.fetch(url)
    fetched = fetcher.fetch((render.REPORTS_DIR / "assets" / "innovaluation-mark.png").as_uri())
    assert fetched is not None


def test_optional_parts_may_be_missing() -> None:
    snapshot = _readiness(compass=None, strengths=[])
    pdf = render_pdf(snapshot)
    text = _text(pdf.data)
    assert "The 12 dimensions" in text
    assert "Strengths" not in text
    assert "AI advice" not in text
    assert pdf.page_count >= 1


def test_long_content_flows_onto_more_pages() -> None:
    snapshot = _readiness()
    long_name = "A very long organisation name " * 6
    snapshot["organisation"]["name"] = long_name.strip()
    priority = deepcopy(snapshot["result"]["priorities"][0])
    snapshot["result"]["priorities"] = [
        {**priority, "rank": i, "next_steps": "Do the next thing well. " * 40} for i in range(1, 6)
    ]
    pdf = render_pdf(snapshot)
    assert pdf.page_count >= 2
    text = _text(pdf.data)
    assert re.search(r"Page 1 of \d", text)
    assert "Confidential." in text


def test_the_same_snapshot_draws_the_same_words() -> None:
    snapshot = _readiness()
    assert _text(render_pdf(snapshot).data) == _text(render_pdf(deepcopy(snapshot)).data)
