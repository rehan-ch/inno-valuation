"""What a PDF report shows, copied from what the app shows for the same result (P7.01).

A snapshot is built from the very payloads the result pages read (``ResultOut``,
``IqAssessmentOut`` and ``AdviceOut``), so every number in the PDF is the number the app
shows. It is stored with the report and never rebuilt: the PDF can be drawn again exactly
as it was, whatever changes later.

AI advice is copied only where the app would show it: the AI is connected, the part has an
answer (the newest one there is), and that answer is not sample text from the development
stand-in. Usage figures
(model, tokens, cost) and anything that depends on who is looking are left out.
"""

from datetime import datetime
from typing import Any, Final

from app.models import Idea
from app.schemas.advice import AdviceOut
from app.schemas.ideas import IqAssessmentOut
from app.schemas.readiness import ResultOut

# The layout a snapshot is drawn with. Raise it when the template changes what it shows,
# and keep drawing older snapshots the way they were drawn.
TEMPLATE_VERSION: Final = 1

ADVICE_PARTS: Final = ("consultation", "interpretation", "recommendations", "gap_actions")


def advice_shown(advice: AdviceOut | None) -> dict[str, Any] | None:
    if advice is None:
        return None
    shown: dict[str, Any] = {}
    for name in ADVICE_PARTS:
        part = getattr(advice, name)
        # As the page shows it: the newest answer there is, even while a newer one is on
        # its way or after asking again failed; never the stand-in's sample text.
        if part.generated_at is not None and not part.sample:
            shown[name] = part.model_dump(mode="json", exclude={"usage", "status", "sample"})
    return shown or None


def _base(
    kind: str, *, organisation: str, requested_by: str | None, generated_at: datetime
) -> dict[str, Any]:
    return {
        "template_version": TEMPLATE_VERSION,
        "kind": kind,
        "organisation": {"name": organisation},
        "requested_by": requested_by,
        "generated_at": generated_at.isoformat(),
    }


def readiness_snapshot(
    *,
    organisation: str,
    requested_by: str | None,
    generated_at: datetime,
    result: ResultOut,
    advice: AdviceOut | None,
) -> dict[str, Any]:
    return {
        **_base(
            "readiness",
            organisation=organisation,
            requested_by=requested_by,
            generated_at=generated_at,
        ),
        "result": result.model_dump(mode="json"),
        "advice": advice_shown(advice),
    }


def iq_snapshot(
    *,
    organisation: str,
    requested_by: str | None,
    generated_at: datetime,
    idea: Idea,
    assessment: IqAssessmentOut,
    advice: AdviceOut | None,
) -> dict[str, Any]:
    return {
        **_base(
            "iq", organisation=organisation, requested_by=requested_by, generated_at=generated_at
        ),
        "idea": {"title": idea.title, "summary": idea.summary, "stage": idea.stage.value},
        "assessment": assessment.model_dump(mode="json", exclude={"can_review"}),
        "advice": advice_shown(advice),
    }
