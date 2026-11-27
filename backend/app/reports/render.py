"""Draw a PDF report from its snapshot (Phase 7, P7.03).

The snapshot holds everything the report shows (app/reports/snapshot.py), so the same
snapshot always gives the same pages: nothing here reads the database or works out a
score. Text is laid out from the Jinja2 template in ``templates/report.html`` and turned
into a PDF by WeasyPrint, with the font and the compass mark bundled in this folder.

The renderer may read only the files in this folder: user text is escaped by the template,
and the fetcher refuses every other address, so a report can never reach the network or
another file on the machine.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final
from urllib.parse import unquote, urlsplit

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from weasyprint import HTML, URLFetcher
from weasyprint.text.fonts import FontConfiguration

from app.reports.compass import compass_svg

REPORTS_DIR: Final = Path(__file__).resolve().parent
TEMPLATE_DIR: Final = REPORTS_DIR / "templates"
PRODUCT_NAME: Final = "InnoValuation"

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=True),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


class _LocalFilesOnly(URLFetcher):  # type: ignore[misc]  # WeasyPrint has no type hints
    """Fetches the bundled font and mark, and nothing else."""

    def fetch(self, url: str, headers: Any = None) -> Any:
        parts = urlsplit(url)
        path = Path(unquote(parts.path)).resolve()
        if parts.scheme != "file" or not path.is_relative_to(REPORTS_DIR):
            raise ValueError(f"A report may not load {url!r}.")
        return super().fetch(url, headers)


@dataclass(frozen=True)
class RenderedPdf:
    data: bytes
    page_count: int


def long_date(value: str) -> str:
    """'19 November 2026' from an ISO date-time, read in UTC like the app's dates."""
    moment = datetime.fromisoformat(value)
    return f"{moment.day} {moment:%B %Y}"


def gap_words(gap: int | None) -> str:
    """The app's wording of a gap (Compass.tsx): target minus score, from the engine."""
    if gap is None:
        return "–"  # noqa: RUF001  (the app's dash for "no target")
    if gap > 0:
        return f"{gap} below target"
    if gap < 0:
        return f"{-gap} above target"
    return "on target"


def money(amount: str, currency: str) -> str:
    """'USD 50,000.00': the amount as the server gave it (already in the currency's minor
    units), with thousands separators and the ISO code."""
    try:
        value = Decimal(amount)
    except InvalidOperation:
        return f"{currency} {amount}"
    decimals = len(amount.split(".")[1]) if "." in amount else 0
    return f"{currency} {value:,.{decimals}f}"


def whole(value: str) -> str:
    """'100' from '100.0': how the app writes the IQ maximum in the compass."""
    return value.split(".", maxsplit=1)[0] if value.rstrip("0").endswith(".") else value


_env.filters.update(long_date=long_date, gap_words=gap_words, money=money, whole=whole)
_env.globals.update(compass_svg=compass_svg, product=PRODUCT_NAME)


def render_html(snapshot: dict[str, Any]) -> str:
    """The report as HTML, before layout. Tests read the numbers from here and from the PDF."""
    return _env.get_template("report.html").render(s=snapshot)


def render_pdf(snapshot: dict[str, Any]) -> RenderedPdf:
    fonts = FontConfiguration()
    document = HTML(
        string=render_html(snapshot),
        base_url=REPORTS_DIR.as_uri() + "/",
        url_fetcher=_LocalFilesOnly(),
    ).render(font_config=fonts)
    data = document.write_pdf()
    if data is None:  # with no target, write_pdf returns the bytes
        raise RuntimeError("WeasyPrint returned no PDF.")
    return RenderedPdf(data=data, page_count=len(document.pages))
