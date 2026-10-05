---
name: ai-touchpoint
description: Scaffold one of the 8 AI touchpoints (prompt template, JSON schema, job, fixtures, tests) in the agreed structure.
argument-hint: <touchpoint number or key>
disable-model-invocation: true
---

Build AI touchpoint $ARGUMENTS as defined in docs/methodology/ai-touchpoints.md.

1. Read that touchpoint's row: when it runs, inputs, output, decides or suggests.
2. Delegate to ai-prompt-engineer: prompt template, JSON schema, job, fixtures, schema test, token note.
3. Delegate to fastapi-dev: the trigger (endpoint or callback), AiRun persistence if missing, serializer for the result.
4. Delegate to frontend-dev only if the touchpoint has a screen (all except 7, the report narrative).
5. Run /spec-check on the new files.
6. Report: where the result is stored, the expected tokens per call, and any PROVISIONAL marker.

Reminders that apply to every touchpoint: the model never computes scores, totals, bands, rankings or VfM; every output item carries dimension_key; touchpoint 3 writes proposals only; user text is delimited as data.
