---
name: decision
description: Record a decision from Amy or Haroon on an open methodology question and push it into the spec and dimensions file.
argument-hint: <Q-id> "<answer>" [by Amy|Haroon]
disable-model-invocation: true
allowed-tools: Bash(touch .claude/.spec-edit-unlocked) Bash(rm -f .claude/.spec-edit-unlocked)
---

Record this decision: $ARGUMENTS

1. Run `touch .claude/.spec-edit-unlocked`. This lets the protect-spec hook allow edits to the signed-off files for this task only.
2. Delegate to spec-keeper with the decision text. It must: mark the Q as DECIDED in docs/methodology/open-questions.md, move the rule into docs/methodology/scoring-spec.md as CONFIRMED, update docs/methodology/dimensions.yml and bump question_set_version if wording changed, then list every file containing `PROVISIONAL: see open-questions <Q-id>`.
3. Run `rm -f .claude/.spec-edit-unlocked`. Do this even if step 2 failed.
4. Show me the list of code changes now needed and ask whether to start them.
