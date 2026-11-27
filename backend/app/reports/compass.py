"""The 12-segment compass, drawn as SVG for the PDF report (P5.03 "same compass in the PDF").

The same drawing as the app's compass (frontend/src/components/compass/Compass.tsx): 12
segments in book order starting at the top, grouped into the 3 categories, each filled as
far as its score is of its maximum, targets as dashed marks, and the headline figure in
the middle. It draws what the snapshot holds and computes no score.
"""

import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

from markupsafe import Markup, escape

SIZE: Final = 420
CENTRE: Final = SIZE / 2
INNER: Final = 64
OUTER: Final = 138
NUMBER_RADIUS: Final = 150
CATEGORY_RADIUS: Final = 163
START_ANGLE: Final = -90  # the first dimension starts at the top
HALF_TURN: Final = 180

# The app's colours (globals.css), as hex for the PDF renderer.
PRIMARY: Final = "#166eb6"
RAMP: Final = ("#9cc9ee", "#2e86d1", "#114a7a")
NEUTRAL_100: Final = "#f0f2f5"
NEUTRAL_300: Final = "#c5ccd3"
NEUTRAL_500: Final = "#6a7481"
NEUTRAL_600: Final = "#4f5a69"
NEUTRAL_900: Final = "#192029"


def _point(radius: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    return CENTRE + radius * math.cos(radians), CENTRE + radius * math.sin(radians)


def _fixed(value: float) -> str:
    return f"{value:.2f}"


def _slice(inner: float, outer: float, start: float, end: float) -> str:
    x1, y1 = _point(outer, start)
    x2, y2 = _point(outer, end)
    x3, y3 = _point(inner, end)
    x4, y4 = _point(inner, start)
    large = 1 if end - start > HALF_TURN else 0
    return " ".join(
        [
            f"M {_fixed(x1)} {_fixed(y1)}",
            f"A {outer} {outer} 0 {large} 1 {_fixed(x2)} {_fixed(y2)}",
            f"L {_fixed(x3)} {_fixed(y3)}",
            f"A {inner} {inner} 0 {large} 0 {_fixed(x4)} {_fixed(y4)}",
            "Z",
        ]
    )


def _arc(radius: float, start: float, end: float, clockwise: bool = True) -> str:
    x1, y1 = _point(radius, start if clockwise else end)
    x2, y2 = _point(radius, end if clockwise else start)
    large = 1 if abs(end - start) > HALF_TURN else 0
    sweep = 1 if clockwise else 0
    return (
        f"M {_fixed(x1)} {_fixed(y1)} "
        f"A {radius} {radius} 0 {large} {sweep} {_fixed(x2)} {_fixed(y2)}"
    )


def _radius_at(value: float, maximum: float) -> float:
    share = max(0.0, min(1.0, value / maximum))
    return INNER + (OUTER - INNER) * share


def fill_of(segment: Mapping[str, Any], level_count: int) -> str:
    """A segment's colour: its level's place on the one-hue ramp, or the one colour when
    the scale has no levels. Chosen by position, so no level is known by name here."""
    level = segment.get("level")
    if not level or level_count == 0:
        return PRIMARY
    place = 1.0 if level_count == 1 else (int(level["order"]) - 1) / (level_count - 1)
    return RAMP[round(place * (len(RAMP) - 1))]


def compass_svg(compass: Mapping[str, Any], *, value: str, maximum: str, label: str) -> Markup:
    """The compass of one result as an SVG element. ``value``, ``maximum`` and ``label``
    are the headline in the middle, as the app shows it ("194", "300", "Building Blocks")."""
    segments: Sequence[Mapping[str, Any]] = compass["segments"]
    categories: Sequence[Mapping[str, Any]] = compass["categories"]
    level_count = len(compass["levels"])
    count = len(segments)
    step = 360 / count
    index = {segment["key"]: i for i, segment in enumerate(segments)}
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
        f'width="{SIZE}" height="{SIZE}" font-family="Plex" class="compass" role="img">'
    ]
    for category in categories:
        places = [index[key] for key in category["dimension_keys"] if key in index]
        if not places:
            continue
        start = START_ANGLE + min(places) * step + 1.5
        end = START_ANGLE + (max(places) + 1) * step - 1.5
        # The category's arc. Its name is in the caption under the drawing: the PDF
        # renderer draws no text along a path.
        parts.append(
            f'<path d="{_arc(CATEGORY_RADIUS, start, end)}" fill="none" stroke="{NEUTRAL_300}" '
            'stroke-width="2" stroke-linecap="round"/>'
        )
    for i, segment in enumerate(segments):
        start = START_ANGLE + i * step
        end = start + step
        nx, ny = _point(NUMBER_RADIUS, start + step / 2)
        score, top = float(segment["score"]), float(segment["maximum"])
        parts.append(
            f'<path d="{_slice(INNER, OUTER, start, end)}" fill="{NEUTRAL_100}" '
            'stroke="white" stroke-width="2"/>'
            f'<path d="{_slice(INNER, _radius_at(score, top), start, end)}" '
            f'fill="{fill_of(segment, level_count)}" stroke="white" stroke-width="2"/>'
        )
        if segment.get("target") is not None:
            radius = _radius_at(float(segment["target"]), top)
            parts.append(
                f'<path d="{_arc(radius, start + 2.5, end - 2.5)}" fill="none" '
                f'stroke="{NEUTRAL_900}" stroke-width="2" stroke-dasharray="3 3"/>'
            )
        parts.append(
            f'<text x="{_fixed(nx)}" y="{_fixed(ny + 4)}" text-anchor="middle" font-size="11" '
            f'fill="{NEUTRAL_500}">{int(segment["order"])}</text>'
        )
    parts.append(
        f'<text x="{CENTRE}" y="{CENTRE - 2}" text-anchor="middle" font-size="30" '
        f'font-weight="600" fill="{NEUTRAL_900}">{escape(value)}</text>'
        f'<text x="{CENTRE}" y="{CENTRE + 17}" text-anchor="middle" font-size="11.5" '
        f'fill="{NEUTRAL_500}">out of {escape(maximum)}</text>'
        f'<text x="{CENTRE}" y="{CENTRE + 33}" text-anchor="middle" font-size="10.5" '
        f'fill="{NEUTRAL_500}">{escape(label)}</text>'
        "</svg>"
    )
    # Safe: every piece of text in the drawing went through escape() above; the rest is
    # numbers and fixed markup.
    return Markup("".join(parts))  # noqa: S704
