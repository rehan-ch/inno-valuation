---
name: review-log
description: Which branches/files the methodology guardian has already cleared, where scoring logic lives, PROVISIONAL marker map, open SPEC GAPs carried forward
metadata:
  type: project
---

Cleared 2026-10-06, branch phase-0-skeleton (no scoring yet): no BLOCK.
- backend/config/ai.yml: 8 keys match ai-touchpoints.md; consultation_nudge had `# PROVISIONAL: see open-questions Q11`. Q11 is DECIDED 2026-10-08 (AI judgement, no threshold): that marker must go when touchpoint 8 is built; re-check ai.yml.

Cleared 2026-10-06, branch phase-1-scoring-engine: no BLOCK, no WARN.

Cleared 2026-10-08, phase-1-scoring-engine (uncommitted, after Amy's 2026-10-08 decisions, commit 516b6d0): no BLOCK, no WARN. 620 tests ~1.5s; ruff + mypy clean.
- Engine files: app/scoring/{question_set,readiness,iq,vfm,categories,priorities,targets,weights,_rounding,_guards,errors}.py.
- Q2 decided: iq.score_iq has NO weights param (keyword-only question_set); IqResult has no weights field. weights.py only validates (Q22 limits).
- Weights used only in priorities._rank_key: (score, -weight [Q23], order [Q19]).
- Current marker map (one each): Q18 `_rounding.ROUNDING`, above `def vfm`, categories.py category 1 decimal (3 distinct sub-rules of Q18, accepted); Q8 above readiness_targets/iq_targets; Q19, Q23, Q21 in priorities.py; Q22 above WEIGHT_LIMITS in weights.py.
- Decided, must have no marker: Q2, Q7, Q9, Q20 (test_source_rules DECIDED_QUESTIONS enforces; EXPECTED_MARKERS + exact-set test is the tripwire).
- SPEC GAP raised 2026-10-08: do weights reorder readiness priorities too, or only IQ priorities? (spec 3.4 is in the IQ section; spec 7 is generic). Code applies to both.
- Advisory carried: vfm() trusts caller to pass IqResult.iq (Q18); weight snapshot per assessment (spec 3.4) is a service-layer job, check when services land.

**Why:** later reviews can skip cleared files unless git diff touches them.
**How to apply:** diff against these files first; when services/AI land, check weights snapshot, ai.yml Q11 marker removal, and that services pass IqResult.iq to vfm.
