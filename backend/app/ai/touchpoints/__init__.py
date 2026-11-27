"""The touchpoints built so far, by key. The AI task looks a run's touchpoint up here."""

from collections.abc import Callable
from typing import Any, Final

from app.ai.runner import Touchpoint
from app.ai.touchpoints import (
    bridge_gaps,
    consultation_nudge,
    explain_question,
    interpret_results,
    propose_iq_scores,
    recommendations,
)
from app.models import AiRun
from app.models.enums import AiTouchpoint

SPECS: Final[dict[AiTouchpoint, Callable[[AiRun], Touchpoint[Any]]]] = {
    AiTouchpoint.EXPLAIN_QUESTION: explain_question.spec_for,
    AiTouchpoint.PROPOSE_IQ_SCORES: propose_iq_scores.spec_for,
    AiTouchpoint.INTERPRET_RESULTS: interpret_results.spec_for,
    AiTouchpoint.BRIDGE_GAPS: bridge_gaps.spec_for,
    AiTouchpoint.RECOMMENDATIONS: recommendations.spec_for,
    AiTouchpoint.CONSULTATION_NUDGE: consultation_nudge.spec_for,
}
