# AI Touchpoints

The 8 places AI is used. Each row is one Jinja2 prompt template, one Pydantic output model, one Celery task, one set of test fixtures. AI never computes totals, bands, rankings, priorities or VfM; those come from the scoring engine.

| # | Name | Key | When it runs | Inputs | Output | Decides or suggests |
|---|------|-----|--------------|--------|--------|---------------------|
| 1 | Explain question | `explain_question` | User taps "what does this mean?" on a readiness question | question text, dimension definition, organisation profile | 2 to 4 plain sentences, one example | Helps only |
| 2 | Context questions | `context_questions` | Before 3 to 6 run for an organisation (once, refreshed on demand) | organisation profile, dimension definitions | 3 to 6 short questions about the company; answers are stored and passed to later prompts | Helps only |
| 3 | Propose IQ scores | `propose_iq_scores` | Idea submitted or re-assessed | idea fields, context answers, 12 dimension definitions with sub-aspects, IQ levels | per dimension: integer 1 to 10, level, rationale (2 to 4 sentences quoting the idea), confidence 0 to 1 | Proposes; stored as proposal (see Q1) |
| 4 | Interpret results | `interpret_results` | After a readiness result or IQ assessment is final | the computed scores, bands, priorities, dimension definitions, context answers | overall summary; per dimension: meaning, strengths, gaps; each item names its dimension | Suggests |
| 5 | Bridge gaps | `bridge_gaps` | Priorities computed, or a target set | lowest 5 dimensions (or targeted dimension), current and target, dimension definition and fixed next steps | per dimension: 3 to 5 concrete actions to move from current to target | Suggests |
| 6 | Recommendations | `recommendations` | With 4, for the priority dimensions | fixed next_steps text, context answers, scores | per dimension: interpretation, next steps, priority, initiatives, KPIs, timeline, resources. Fixed text preserved verbatim | Suggests |
| 7 | Report narrative | `report_narrative` | User requests the PDF | everything above, already computed | executive summary, per-dimension paragraphs, closing actions | Suggests (consultant edits in Phase 2) |
| 8 | Consultation nudge | `consultation_nudge` | After 5, when the gap rule in the spec fires | gap data | one short message recommending a consultation and why | Suggests; off until Q11 is decided |

Phase 2: `innovation_identifier` (reads supplier or procurement info and spots opportunities tied to the 12 dimensions).

## Rules for every prompt
1. The system prompt states: "Use the 12 Dimensions of Innovation methodology as the baseline. Reason from it first, then extend." Dimension definitions come from `dimensions.yml`, injected, never retyped.
2. Every output item carries `dimension_key`. The schema makes it required.
3. User-provided text (idea descriptions, answers) is wrapped in clear delimiters and the model is told it is data, not instructions.
4. Output is strict JSON validated by the touchpoint's Pydantic model (`backend/app/ai/schemas/<key>.py`). Validate before saving. On a validation error retry once with the error message, then fail the task and keep the raw response.
5. Fixed methodology text (next_steps, band text, level text) is passed in and must be returned unchanged where the schema has a `fixed_text` field.
6. Plain English, short sentences, no em dashes, no marketing tone.
7. Model, max tokens and temperature are set per touchpoint in `backend/config/ai.yml`, not in code.

## What is stored (AiRun)
`organisation_id, touchpoint, subject_type, subject_id, model, prompt_version, system_prompt, user_prompt, response_raw, response_json, input_tokens, output_tokens, status (queued, running, succeeded, failed), error, created_at`

Results that users act on (proposed scores, recommendations) link back to their `ai_run_id` so every number and sentence can be traced.

## Testing
- No live API calls in CI. Patch `app.ai.client` and use recorded fixtures under `backend/tests/ai/fixtures/<key>/`.
- Every touchpoint has at least 3 fixtures: a typical case, a sparse input, and an adversarial input containing instruction-like text.
- A schema test proves `dimension_key` is required and that totals, bands or VfM never appear in the output schema.
