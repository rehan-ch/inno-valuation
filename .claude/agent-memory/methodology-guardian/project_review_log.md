---
name: review-log
description: Which branches/files the methodology guardian has already cleared, where scoring logic lives, PROVISIONAL marker map, open SPEC GAPs carried forward
metadata:
  type: project
---

Cleared 2026-10-06, branch phase-0-skeleton (no scoring yet): no BLOCK.
- backend/config/ai.yml: 8 keys match ai-touchpoints.md exactly; consultation_nudge `enabled: false  # PROVISIONAL: see open-questions Q11` (only place Q11 appears).
- frontend/src (page, layout, health page, HealthStatus, api client): health-check copy only.

Cleared 2026-10-06, branch phase-1-scoring-engine (uncommitted tree): no BLOCK, no WARN. 504 engine tests in ~2.5s; ruff + mypy clean.
- Engine files: app/scoring/{question_set,readiness,iq,vfm,categories,priorities,targets,_rounding,_guards,errors}.py.
- PROVISIONAL marker map (all one place each): Q18 rounding mode `_rounding.py ROUNDING`; Q2 `iq._validated_weights` + `iq._weighted_iq`; Q7 + Q18(VfM uses rounded IQ) above `def vfm`; Q9 above `readiness_categories` and `iq_categories`; Q20 + Q18(category 1 decimal) inside `iq_categories`; Q8 above `readiness_targets`/`iq_targets`; Q19 inline on sort key in `priorities._lowest_dimensions`.
- tests/scoring/test_source_rules.py asserts every marker string verbatim + bans dimension/band/level literals in engine source. If a marker moves, that test fails: good tripwire.
- Phase-0 WARN on test_boundaries.py (relative imports, missing anthropic/fastapi/celery) is FIXED.
- Advisory only (not findings): vfm() accepts any Decimal IQ, so Q18 "rounded IQ" relies on callers passing IqResult.iq; IQ in (0,10) accepted though spec range is 10 to 100.
- SPEC GAP raised: spec 7 "Normally the lowest 5": is it ever not 5? Check if a Q21 was added.

**Why:** later reviews can skip cleared files unless git diff touches them.
**How to apply:** on the next branch, diff against these files first; re-verify marker map if services start calling the engine (services must pass IqResult.iq to vfm).
