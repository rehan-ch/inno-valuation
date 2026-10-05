---
name: new-feature
description: Standard delivery pipeline for one InnoValuation feature. Spec, open questions, plan, implement with the right agents, test, spec-check, code review, summary.
argument-hint: <feature name or ticket>
disable-model-invocation: true
---

Deliver this feature end to end: $ARGUMENTS

Follow every step in order. Do not skip a step because it looks small.

1. Spec. Read the sections of docs/methodology/scoring-spec.md, docs/methodology/ai-touchpoints.md and docs/architecture/data-model.md that this feature touches. Quote the relevant lines.
2. Open questions. Grep docs/methodology/open-questions.md for anything this feature depends on. If an OPEN question blocks the feature, stop and tell me which one. If it only affects a detail, continue with the provisional default and name the Q number.
3. Plan. Write a short plan: files to add or change, API contract, data changes, tests. Ask me to confirm before writing code.
4. Implement. Delegate by area: scoring math to scoring-engine-dev, server work to fastapi-dev, UI to frontend-dev, prompts and AI jobs to ai-prompt-engineer. Run independent parts in parallel. Each agent must follow its own checklist.
5. Test. Use test-runner. Fix failures. Repeat until green.
6. Spec check. Run /spec-check on the changed files. Fix every BLOCK, then re-run.
7. Review. Use code-reviewer. Fix every Critical.
8. Summary. List: what shipped, spec sections implemented, PROVISIONAL markers added (with Q numbers), new open questions raised, and how to try the feature by hand.
