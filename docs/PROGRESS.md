# Progress

## Phase and branch
- Phases 0 to 2 are merged to `main` (Phase 2 through PR 1, the password follow-up through PR 2).
- Phase 3's readiness flow is merged to `main` (PR 3). Its AI work (P3.05, P3.06) is on `phase-3-ai`.

## In progress
Phase 3 AI on `phase-3-ai`
- Done (P3.05, AI foundation): the `ai_runs` table (migration `0007_ai_runs`) logs every AI result with its prompts, model asked and model that answered, effort, prompt version, raw and validated answer, attempts, tokens, cost (millionths of a dollar at the list prices in `config/ai.yml`) and the API request id of each attempt. `app/ai/`: `config.py` (strict loader for `config/ai.yml`, now `effort` instead of `temperature`), `client.py` (Anthropic SDK with structured JSON output, timeouts, SDK retries with backoff, refusal fallback; offline stand-in without a key in development and tests; fails loudly when deployed without one), `prompting.py` (Jinja2 templates with a version line, `as_data` delimiting), `runner.py` (validate, retry once with the reason, then fail and keep the raw answer), `schemas/` (strict output models, `dimension_key` required), the Celery task `ai.run` (ids only, re-checks the organisation, idempotent).
- Done (P3.06, explain a question): "What does this mean?" under every question for people who answer. `POST /api/v1/readiness/questions/{id}/explanation` asks (or returns the organisation's saved one), `GET` polls; 2 to 4 plain sentences and one example, naming the dimension; saved per organisation and question, reused while the prompt and company details are unchanged; 150 runs per organisation per day. Recorded cases: typical, sparse, adversarial (and the model obeying the injection, which the schema refuses), retry.
- Done: security bumps the audits caught, which also affected `main`: Next.js 16.4.3 (critical advisories) and `opentelemetry-api` 1.45.1.
- Next: review and merge `phase-3-ai`, then Amy's first demo (P3.08). Until the AI key arrives, explanations show marked sample text.

Phase 3 readiness flow (merged)
- Done: readiness tables and reversible migration `0006_readiness` (P3.01): assessments, per-person responses, consensus with per-question notes, results; answers checked 1 to 5 in the database (strict jsonpath); assessment permissions added to the matrix (`assessments.view` for every role including consultants, `assessments.answer` for owner/admin/member/committee, `assessments.manage` for owner/admin).
- Done: the readiness flow, backend and screens (P3.02 to P3.04). API `/api/v1/readiness`: the question set verbatim from the book; start an assessment (one open per organisation); each person saves their own answers as they go and submits all 60; the facilitator starts consensus, sees every submitted answer with the mean (2 decimals) and spread, sets agreed answers and notes, and finalises; the engine scores the agreed answers only and the result is written once. Screens: `/readiness` (list and start), `/readiness/[id]` (questionnaire with autosave, per-dimension progress, submit; the facilitator's team progress and start consensus), `/readiness/[id]/consensus`, `/readiness/[id]/result` (total out of 300 with the band in the book's words, categories with maximums, the 12 dimensions, priorities with the book's next steps, strengths). The dashboard's readiness card and checklist use the real status.
- Done (P3.07): request tests for the golden flow (three people, agreed total 190, Building Blocks), immutability, missing participants, rounding, permissions and cross-organisation isolation; exercised end to end against the running stack.

## Done
Phase 0
- `bf47845` chore(skeleton): backend (FastAPI, settings, sync SQLAlchemy, Alembic baseline, error envelope, Celery ping), frontend (Next 16, `/health`, typed client, Vitest), CI, `bin/setup`, `bin/dev`, docker compose.
- `e7f925a` fix(dev): `bin/dev` no longer shell-sources `.env`.
- `e65ec2f` test(scoring): import boundary test resolves relative imports and bans AI, web and job modules.
- `d7b4622` fix(skeleton): review fixes (CORS on 500s, secret key check, DB connect timeout, localhost-only services, CI hardening, script fixes).
- `8622ca5` docs(progress): Phase 0 complete.
- `aed55fe` build(hooks): pre-commit, commit-msg and pre-push gates in `.githooks/`, all logic in `bin/check`; stricter ruff and TypeScript rules; CI mirrors the new checks (lock file, migrations, dependency audits).
- Gate: code-reviewer "Ready to merge: yes"; methodology-guardian no BLOCK.

Phase 1
- `211616d` feat(scoring): `question_set`, `readiness`, `iq`, `vfm`, `priorities`, `categories`, `targets`, `errors`, plus `_rounding` (one fixed Decimal context) and `_guards` (question set version check). 548 engine tests, about 4 s.
- Gate: methodology-guardian 0 BLOCK, 0 WARN. code-reviewer "Ready to merge: yes"; its should-fix items (float and unbounded weights, VfM input bounds) and nits applied before the commit.
- `9e450ee` chore(git): ignore local `ask-amy/` drafts.
- `516b6d0` docs(methodology): Amy's answers recorded (Q1, Q2, Q5, Q7, Q9, Q11, Q12, Q16 decided; Q20 follows from Q2; Q23 new).
- Engine follow-up (next commit): weights never change the IQ (Q2). `score_iq` has no weights; weight validation moved to `app/scoring/weights.py` (`validate_weights`, read-only snapshot); priorities take optional weights as a tie-break after score and before book order (Q23). 621 engine tests. Gate: methodology-guardian 0 BLOCK, 0 WARN; code-reviewer "Ready to merge: yes".

## Done, Phase 2 (merged)
- Done: accounts tables and migrations (`0002` to `0005`); email and password sign-up, verification, sign-in, reset and change password; sessions, CSRF, sign-in throttling; roles and permissions; company separation; creating an organisation; team (members, roles, removal, owner rules); invitations (invite, list, cancel, preview, accept); consultant access (grant with end date, change, revoke, accept, switcher).
- Done (screens): shared UI components (`frontend/src/components/ui/`), API client with the CSRF header and typed wrappers per backend router (`frontend/src/lib/api/`), and the pages: sign-up, sign-in, verify email (including choose-a-password links), forgot and reset password, invitation accept, the signed-in shell with the organisation switcher, team (invite, cancel, change role, remove), consultant access (client admin side and the consultant's own page), account, create organisation, and organisation settings (profile and currency). Email-link tokens travel in the URL fragment and the sign-in redirect preserves it. 61 frontend tests; the whole flow (sign-up to consultant grant) exercised by hand against the live API.
- Done (design system, P2.08): design tokens and the documented type and spacing scale in `globals.css`; Table, Modal, Drawer and EmptyState components; a spinner in Loading; skip-to-content link, `aria-current` navigation and `id="main"` landmarks.
- Day 4 review of the screens applied: open-redirect guard on `?next=`, strict-mode-safe reset-password token read, Modal padding clicks, UTC date rendering, functional list state updates, a re-entry guard in `useSubmit`, sign-out failure handling, and client-side guards on the consultant end-date fields.
- Google sign-in: dropped from the MVP (Haroon's call on the P2.02 card); the backend user model keeps the sign-in-method column, so it can be added later without a migration.
- Field-level form validation (email shape, password minimum, organisation name and currency) and the NIST-style password policy: no composition rules, the NCSC common-password list and context words refused with clear messages; minimum 8 characters.
- Still open on P2.07: Amy tries the demo (sign in, invite a team).

## Decided by Amy (2026-10-08)
- Q1 AI proposes IQ scores, the owner confirms or changes them. Q2 weights never change the IQ, only the priority order. Q5 a facilitator sets the agreed answer. Q7 cost is the planned or known investment; procurement VfM is total purchase value / IQ. Q9 category scores. Q11 the AI judges when to suggest a consultation (built with touchpoint 8, Phase 6). Q12 the client admin invites the consultant, with an end date. Q16 the Version 1 feature list. Q20 follows from Q2.
- Team decisions (not sent to Amy, see `docs/decisions.md`): currency USD by default with a per-organisation setting; Q6 one full assessment; Q4 no per-dimension labels in Version 1.

## PROVISIONAL markers in code
- Q8: `backend/app/scoring/targets.py` (per dimension, both scales).
- Q10: `backend/app/ai/touchpoints/explain_question.py` `COMPANY_FIELDS` (only industry, size and country go to the AI provider).
- Q17: `frontend/src/app/globals.css` (ice-blue and emerald palette from the compass mark, pending Amy's approval).
- Q11: `backend/config/ai.yml` (consultation nudge off until touchpoint 8 is built; Q11 itself is decided).
- Q18: `backend/app/scoring/_rounding.py` (half up), `vfm.py` (uses the rounded IQ), `categories.py` (category IQ 1 decimal).
- Q19: `backend/app/scoring/priorities.py` (ties in book order).
- Q21: `backend/app/scoring/priorities.py` `PRIORITY_COUNT = 5`.
- Q22: `backend/app/scoring/weights.py` `WEIGHT_LIMITS` (0 to 1000, at most 6 decimals).
- Q23: `backend/app/scoring/priorities.py` (weight breaks ties after score, before book order; IQ list only for now).

## Open questions
- Still OPEN in `docs/methodology/open-questions.md`: Q3, Q4, Q6, Q8, Q10, Q13 to Q15, Q17 to Q19, Q21 to Q23. Q3, Q4 and Q6 are settled informally (see above) and should be closed with `/decision` when convenient.
- Q23 is the only new methodology question for Amy: how weights reorder priorities, and whether readiness priorities use them too. Ask it together with Q19 if needed.

## Known gaps
- `.env.example` has `EMAIL_FROM=InnoValuation <no-reply@example.com>` unquoted. Harmless now (nothing shell-sources `.env`), but it should be quoted. Agents cannot edit `.env.*` (project permission rule), so a human must change it.
- CI workflow is written but has never run (no remote).
- `npm audit`: 5 findings (3 high, 2 moderate) in dev-only lint dependencies (eslint-config-next). Production dependencies have none; the pre-push and CI audits check production only.
- AI test fixtures are hand-written in the model's output format. Replace them with live recordings once the AI key arrives, and try the explain prompt on a few real questions.
- The backend Docker image (Phase 8) must ship `docs/methodology/dimensions.yml` and set `INNO_QUESTION_SET_PATH`, and must ship `backend/config/ai.yml` and `backend/app/ai/prompts/`.
- Services built in later phases must pass `IqResult.iq` (already rounded) to `vfm`, so VfM always uses the IQ the user sees (Q18).

## How to run and try it manually
```bash
bin/setup                    # once on a fresh clone; also enables the git hooks
bin/dev                      # API :8000, Celery worker, Next.js :3000
open http://localhost:3000/health
bin/test-scoring             # engine tests, no database
bin/check full               # everything the pre-push hook runs
cd backend && uv run pytest  # full suite (needs docker compose services)
cd frontend && npm test
```
Try the engine by hand:
```bash
cd backend && uv run python -c "
from decimal import Decimal
from app.scoring.question_set import QUESTION_SET as Q
from app.scoring import readiness, iq, vfm
r = readiness.score_readiness({qid: 4 for d in Q.dimensions for qid in Q.question_ids(d.key)})
print(r.total, r.band.name)                                  # 240 Building Blocks
result = iq.score_iq({d.key: 7 for d in Q.dimensions})
print(result.iq, vfm.vfm(5_000_000, 2, result.iq))           # 70.0 714.29
"
```
