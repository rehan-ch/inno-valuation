---
name: review-log
description: Which branches/files the methodology guardian has already cleared, and open WARN items carried forward
metadata:
  type: project
---

Cleared 2026-10-06, branch phase-0-skeleton (no scoring yet): no BLOCK.
- backend/config/ai.yml: 8 keys match ai-touchpoints.md exactly; consultation_nudge `enabled: false  # PROVISIONAL: see open-questions Q11` (only place Q11 appears).
- backend/app/scoring/__init__.py: docstring only, pure.
- frontend/src (page, layout, health page, HealthStatus, api client): health-check copy only, no numbers, no dimension lists, no em dashes.

Open WARN carried forward (re-check on next review):
- backend/tests/scoring/test_boundaries.py skips ALL relative imports (`if node.level: continue`), so `from .. import db` (level>=2) escapes app.scoring undetected. FORBIDDEN also lacks `anthropic`, `fastapi`, `celery`, `app.services`, `app.api`.
- Spec section 11 golden examples have no tests yet (expected until the engine lands; becomes a hard check then).

**Why:** later reviews can skip cleared files unless git diff touches them.
**How to apply:** on the next branch, diff against these files first; confirm the boundary-test WARN was fixed.
