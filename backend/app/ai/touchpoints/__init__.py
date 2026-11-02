"""The touchpoints built so far, by key. The AI task looks a run's touchpoint up here."""

from collections.abc import Callable
from typing import Any, Final

from app.ai.runner import Touchpoint
from app.ai.touchpoints import explain_question, propose_iq_scores
from app.models import AiRun
from app.models.enums import AiTouchpoint

SPECS: Final[dict[AiTouchpoint, Callable[[AiRun], Touchpoint[Any]]]] = {
    AiTouchpoint.EXPLAIN_QUESTION: explain_question.spec_for,
    AiTouchpoint.PROPOSE_IQ_SCORES: propose_iq_scores.spec_for,
}
