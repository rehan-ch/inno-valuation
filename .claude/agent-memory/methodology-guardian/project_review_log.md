---
name: review-log
description: Which branches/files the methodology guardian has already cleared, where scoring logic lives, PROVISIONAL marker map, open SPEC GAPs carried forward
metadata:
  type: project
---

Cleared 2026-10-06, branch phase-0-skeleton (no scoring yet): no BLOCK.

Cleared 2026-10-08, phase-1-scoring-engine (after Amy's 2026-10-08 decisions, commit 516b6d0): no BLOCK, no WARN.

Pre-merge 2026-10-12, phase-1-scoring-engine at 497ec12 vs main: no BLOCK, 2 WARN. 621 tests ~1.7s.
- WARN: backend/config/ai.yml:36 still `# PROVISIONAL: see open-questions Q11` though Q11 is DECIDED (AI judgement). test_source_rules only scans app/scoring, so config/ is not covered.
- WARN (low): weights.py:84-85 rejects all-zero weights; not in Q22 provisional default text. Fix: add to Q22 default or drop the check.
- Engine files: app/scoring/{question_set,readiness,iq,vfm,categories,priorities,targets,weights,_rounding,_guards,errors}.py.
- Q2 decided: iq.score_iq has NO weights param; IqResult has no weights. weights.py only validates (Q22).
- Weights used only in priorities._rank_key: (score, -weight [Q23], order [Q19]).
- Marker map (EXPECTED_MARKERS in tests/scoring/test_source_rules.py is the tripwire): Q18 x3 (_rounding.ROUNDING, above def vfm, categories.py:110 category 1 decimal; 3 distinct sub-rules, accepted); Q8 above readiness_targets/iq_targets (accepted); Q19, Q23, Q21 in priorities.py; Q22 above WEIGHT_LIMITS.
- Decided, must have no marker: Q1, Q2, Q5, Q7, Q9, Q11, Q12, Q16, Q20.
- Earlier SPEC GAP (do weights reorder readiness priorities?) is now Q23 part 2. Q23 default: IQ list only, enforced in services. Spec 7 text does not yet mention that scope; align on /decision.
- Advisory for services phase: weights passed only to iq_priorities (Q23 default, one place); weights snapshot per assessment (spec 3.4); vfm gets IqResult.iq (Q18).

**Why:** later reviews can skip cleared files unless git diff touches them.
**How to apply:** diff against these files first; when services/AI land, check the advisories above and that the ai.yml Q11 marker is gone.
