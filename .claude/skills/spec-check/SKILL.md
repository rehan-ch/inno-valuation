---
name: spec-check
description: Check code, prompts or UI against the scoring spec. Use after changing anything that produces or displays a number, before any merge.
argument-hint: [files or feature name]
context: fork
agent: methodology-guardian
background: false
---

Check the following against docs/methodology/scoring-spec.md, docs/methodology/dimensions.yml and docs/methodology/open-questions.md:

$ARGUMENTS

If nothing was given above, check every file in `git diff --name-only HEAD` plus untracked files from `git status --porcelain` that touch scoring, readiness, IQ, VfM, weights, bands, labels, priorities, prompts, dashboard numbers or PDF numbers.

Return BLOCK, WARN and OK findings with file:line, the spec section, and the smallest fix.
