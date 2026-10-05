---
name: kickoff
description: Master instructions to start or resume the InnoValuation build. Reads the docs and PROGRESS.md, plans the current phase, then executes it with the project agents and skills. Run at the start of every session.
argument-hint: [phase number, or "continue"]
disable-model-invocation: true
---

Requested scope for this session: $ARGUMENTS
If a phase number is given, work on that phase. If "continue" is given, finish the current phase and move to the next. If nothing is given, resume from docs/PROGRESS.md, or start Phase 0 when it does not exist.

# InnoValuation build: master instructions for Claude Code

You are the lead engineer on InnoValuation, an innovation diagnostic platform built on Amy-Renee's "12 Dimensions of Innovation" methodology. You coordinate the subagents in `.claude/agents/` and use the skills in `.claude/skills/`. I (Ninja) am the developer and reviewer. Haroon is the product owner. Amy is the methodology owner and is not in this chat; her undecided rules are tracked in `docs/methodology/open-questions.md`.

Your job is to take the project from an empty repository to a working, tested, deployable Version 1, one phase per session, following the plan below exactly.

## 1. Before you do anything in this session

1. Read `CLAUDE.md` in full. It holds the non-negotiable rules, the stack, the repository layout and the conventions. Everything you build must follow it.
2. Read `docs/methodology/scoring-spec.md`, `docs/methodology/open-questions.md`, `docs/methodology/ai-touchpoints.md`, `docs/methodology/prototype-review.md` and `docs/architecture/data-model.md`.
3. Read `docs/PROGRESS.md` if it exists. It says where the previous session stopped and what is next. If it does not exist, you are starting Phase 0.
4. Run `git status` and `git log --oneline -15`. Work on a branch named `phase-<n>-<slug>`, never on `main`.
5. Reply with a plan of at most 12 lines: which phase you are on, the features in it, the open questions it touches and the provisional defaults you will use. Then start. Do not ask me anything the documents already answer.

## 2. How to work

- One phase per session, in order, unless I say "continue to the next phase". Inside a phase, run `/new-feature <feature>` for each feature listed, in the order listed.
- Delegate by area and let agents run in parallel when the work is independent:
  - scoring math: `scoring-engine-dev`
  - server side (models, Alembic, routers, dependencies, services, Celery tasks, PDF, email): `fastapi-dev`
  - UI: `frontend-dev`
  - prompts, Pydantic output models, touchpoint runners, AI fixtures: `ai-prompt-engineer`
  - running tests: `test-runner`
  - before every merge: `/review-pr` (runs `code-reviewer` and `methodology-guardian`, then tests)
- Open questions never block you. Use the provisional default written in `docs/methodology/open-questions.md`, implement it in one named constant with the comment `PROVISIONAL: see open-questions Qn`, and keep going. When you find a new ambiguity, ask the `spec-keeper` agent to add it to `open-questions.md` with a provisional default, then continue.
- Decisions inside the stack (a library within the stack, file naming, layout details, error codes) are yours. Decide, write one line in `docs/decisions.md` (date, decision, reason), move on. Do not ask me.
- Ask me only when: (a) you need a credential or external account (Anthropic API key, Google OAuth client, Resend key, production database or Redis), (b) two documents contradict each other, (c) an acceptance check cannot pass without a product decision that has no provisional default. When you ask, give me the options and your recommendation in one message.
- Scope is the Version 1 list in Q16's provisional default. Never build anything listed in `scoring-spec.md` section 12 ("not part of the methodology"). Never build Phase 2 items (action plans with owners, innovation identifier, booking, payments, consultant overrides, benchmarks) unless I ask.
- The Emergent prototype, if present at `reference/prototype/`, is a UX reference only. Use `/prototype <screen>` to look at layouts. Never copy its scoring logic, readiness dimensions, tiers or grades.
- Quality gates for every feature before you call it done: tests green, `uv run ruff check .` and `uv run mypy app` clean, `/spec-check` returns no BLOCK, `/review-pr` says "Ready to merge: yes", and a cross-organisation 404 test exists for every new client table.
- No live AI calls in tests. Patch `app.ai.client` and use recorded fixtures.
- All UI copy and AI-facing text: simple English, short sentences, no em dashes.
- Commit after every feature with `type(scope): summary`. Push the branch if a remote exists.

## 3. Session end and hand-over

Before the session ends, when I say "pause", or when you notice the context getting long, write `docs/PROGRESS.md` with these sections: Phase and branch, Done (features with commit hashes), In progress (exact next step), PROVISIONAL markers added (Q numbers and files), New open questions, Known gaps, How to run and try it manually. Commit it. The next session starts from that file.

At the end of each phase, give me a summary in this exact shape: Done, Not done, PROVISIONAL markers (Q numbers), New open questions, How to try it, Next phase.

## 4. Environment

- Local development through `docker compose` (Postgres, Redis) and `bin/dev` (uvicorn with reload, Celery worker, Next.js dev server). `bin/setup` prepares everything on a fresh clone.
- `.env.example` lists every variable with a comment. `.env` is never committed.
- Model IDs, max tokens and temperature per AI touchpoint live in `backend/config/ai.yml`. Never hardcode a model name in code. If you are unsure which current model IDs to put there, ask me once.
- Tests use a throwaway Postgres database per run. Celery runs eagerly in tests.

## 5. The phases

### Phase 0: Skeleton (branch `phase-0-skeleton`)
Deliver:
- Repository layout exactly as `CLAUDE.md` describes. `backend/` as a `uv` project (Python 3.12), `frontend/` as a Next.js TypeScript app with Tailwind.
- FastAPI app with `GET /api/v1/health`, settings via pydantic-settings, SQLAlchemy sync session with `get_db`, Alembic configured, one empty baseline migration, the single error handler with the error envelope from `CLAUDE.md`.
- Celery app with Redis broker and a `ping` task. Eager mode in tests.
- pytest with a throwaway database fixture, factory-boy, httpx `TestClient` fixture, `tests/scoring/` folder with one placeholder test so `bin/test-scoring` runs.
- ruff and mypy configured and passing. GitHub Actions workflow running lint, types and tests on push.
- Frontend `/health` page that calls the API, typed API client, Vitest configured with one test.
- `docker-compose.yml` (postgres, redis), `bin/setup`, `bin/dev`, `.env.example`, `README.md` with run instructions.
- `docs/PROGRESS.md` and `docs/decisions.md` created.
Accept when: a fresh clone can run `bin/setup` then `bin/dev`; `uv run pytest`, `npm test`, ruff, mypy and CI are all green.

### Phase 1: Scoring engine (branch `phase-1-scoring-engine`)
Deliver, all inside `backend/app/scoring/` and `backend/tests/scoring/`, through `scoring-engine-dev`:
- `question_set.py`: loads `docs/methodology/dimensions.yml` once, exposes `QuestionSet` with version, ordered dimensions, categories, bands and levels, and a validator that every dimension has 5 questions.
- `readiness.py`, `iq.py`, `vfm.py`, `priorities.py`, `categories.py` (PROVISIONAL Q9), `targets.py` (PROVISIONAL Q8), `errors.py` with `ScoringError`. Frozen dataclass result types. `Decimal` where rounding matters.
- Tests: every golden example from `scoring-spec.md` section 11, every band and level boundary (below, on, above), partial input giving `complete=False`, invalid values raising `ScoringError`, weights not summing to 1 (PROVISIONAL Q2), IQ of 0 giving VfM `None`, and `test_boundaries.py` proving the package imports nothing from `sqlalchemy`, `app.models`, `app.db`, `app.ai`, `httpx` or `requests`.
Accept when: `bin/test-scoring` runs green in under 10 seconds and `/spec-check backend/app/scoring` returns no BLOCK and no WARN.

### Phase 2: Accounts, organisations and roles (branch `phase-2-accounts`)
Deliver:
- Tables: `organisations`, `users`, `memberships` (roles: owner, admin, member, committee, investor, consultant, tech_admin), `consultant_grants`, `invitations`. Alembic migrations with indexes and constraints.
- Auth: Google sign-in through Authlib, email and password with argon2, JWT in an httpOnly cookie, sign out. Provisional per Q14 (both methods).
- Dependencies in `app/core/deps.py`: `current_user`, `current_org`, `require_role(...)`. Consultant access only through a live `ConsultantGrant`.
- Endpoints: sign up, sign in, sign out, `GET /me`, create organisation, update profile (industry, size, revenue band, founders), invite member (email through Resend in a Celery task), accept invitation, list members, change role, remove member, create and revoke consultant grant with expiry (PROVISIONAL Q12).
- Frontend: sign in and sign up pages, organisation create, organisation switcher, team page with invite and roles, consultant access page.
Accept when: tests prove a user in organisation A gets 404 for every organisation B resource, role tests pass for each protected route, the invitation email task runs eagerly in tests, and `/review-pr` is green.

### Phase 3: Readiness assessment (branch `phase-3-readiness`)
Deliver:
- Tables: `readiness_assessments`, `readiness_responses` (one per respondent, answers as JSONB, check constraint 1 to 5), `readiness_consensus` (PROVISIONAL Q5), `readiness_results` (immutable once final). All store `question_set_version`.
- Endpoints: start assessment, autosave own answers (PATCH, partial allowed), submit own response, consensus view (per question: each respondent's answer, mean to 2 decimals, spread), set consensus answers (owner or admin), finalise (service calls `app.scoring.readiness`, stores per-dimension scores, category totals, total, band, priorities), list and fetch past assessments.
- AI touchpoint 1 (explain a question): enqueue a Celery task, poll for the result, cache per organisation and question. Built through `/ai-touchpoint 1`.
- Frontend: questionnaire with progress per dimension, debounced autosave showing "Saved", resume later, "your answers" and "team consensus" views, consensus page for the facilitator, result page showing the band text exactly as written and 12 dimension cards with the score out of 25.
Accept when: an end-to-end test with 3 respondents, consensus answers, total 190 and band "Building Blocks" passes; a test proves a final result cannot be modified; `/spec-check` is clean.

### Phase 4: Ideas and IQ (branch `phase-4-ideas-iq`)
Deliver:
- Tables: `ideas` (money as integer minor units plus currency), `iq_assessments` (status proposed or confirmed, weights snapshot, `question_set_version`), `dimension_scores` (proposed score, rationale, confidence, `ai_run_id`, final score, level, edited_by), `vfm_snapshots`, `ai_runs`, `context_answers`.
- AI touchpoint 2 (context questions about the company) and touchpoint 3 (propose 12 scores with rationale and confidence), built through `/ai-touchpoint 2` and `/ai-touchpoint 3`. Low temperature for touchpoint 3. Fixtures: typical, sparse, adversarial.
- Confirm flow (PROVISIONAL Q1, option b): the owner reviews the 12 proposals, edits any, confirms. The service then calls `app.scoring.iq`, levels, categories (PROVISIONAL Q9), `vfm` and `priorities`, and stores everything. Re-assessing creates a new `iq_assessment`; old ones stay.
- Weights settings per organisation (PROVISIONAL Q2 weighted formula), snapshotted on each assessment.
- Endpoints: create idea, trigger scoring, poll proposal status, edit proposals, confirm, list ideas with IQ and VfM, compare and sort.
- Frontend: idea form, "AI suggests, you confirm" screen with the rationale beside each score and a "Proposed by AI" label, ideas list sortable by IQ and VfM, weights page.
Accept when: an end-to-end test with a recorded AI fixture passes this exact case: 12 proposed scores summing to 83, the user changes Organizational Agility from 4 to 5, final IQ 70.0, VfM 714.29 for a cost of 50,000; schema tests prove `dimension_key` is required and no total, band or VfM field exists in any AI output model; no live API in CI.

### Phase 5: Dashboard and compass (branch `phase-5-dashboard`)
Deliver:
- Dashboard with two separate headline cards: organisation Readiness (total out of 300 and band) and the selected idea's IQ (out of 100). Never a combined number.
- Compass or radar: 12 segments in book order, grouped by the 3 categories, category aggregates shown, colour from the band or level supplied by the API, legend, keyboard accessible, table alternative.
- Dimension drill-down: score, level or band text as written, fixed `next_steps` text, placeholders for the AI text that arrives in Phase 6.
- Priorities list (lowest 5). Targets per dimension on both scales (PROVISIONAL Q8) with the gap shown.
- History: compare final readiness results and confirmed IQ assessments over time per dimension, with up or down indicators, same `question_set_version` only.
Accept when: frontend tests cover the two cards and the compass rendering from API data with no hardcoded dimension list; a grep test proves the frontend contains no scoring formula; `/review-pr` is green.

### Phase 6: AI interpretation and recommendations (branch `phase-6-ai-advice`)
Deliver:
- Touchpoints 4 (interpret results), 5 (bridge gaps for the 5 priorities and any target), 6 (recommendations with the fixed `next_steps` text preserved unchanged) and 8 (consultation nudge, off until Q11, PROVISIONAL). Built through `/ai-touchpoint`.
- Tables: `interpretations`, `recommendations`, each linked to its `ai_run_id`.
- Frontend: AI text blocks on the result and drill-down pages, each labelled with its dimension and "Proposed by AI", a regenerate button, token usage visible to tech_admin.
Accept when: a validator test proves `fixed_text` is returned unchanged; every output item carries a valid `dimension_key`; fixtures exist for typical, sparse and adversarial inputs; `/spec-check` is clean.

### Phase 7: Reports (branch `phase-7-reports`)
Deliver:
- Touchpoint 7 (report narrative). `reports` table with a JSONB snapshot of everything rendered.
- Jinja2 HTML template rendered to PDF with WeasyPrint in a Celery task, for a readiness result and for an idea. InnoValuation branding with the compass mark; neutral palette (PROVISIONAL Q17).
- Download endpoint that checks the organisation, "your report is ready" email through Resend.
Accept when: a test proves every number in the PDF snapshot equals the API numbers for the same result; PDFs render for both subjects; `/review-pr` is green.

### Phase 8: Hardening and deployment (branch `phase-8-hardening`)
Deliver:
- Rate limiting on AI-triggering endpoints, request size limits, audit of logs for idea text or answers (none allowed), security headers, CORS locked to the frontend origin.
- Opt-in seed command creating one demo organisation with the "Fresh Tiffin" example idea and a completed readiness assessment. Never auto-seeded for real users.
- Dockerfiles for backend and frontend, Procfile or compose for Heroku or AWS, health checks, backup note, deployment steps in `README.md`.
- Run `/methodology-audit` and fix every BLOCK. Run `/dimension-content-check` if `reference/book.txt` exists.
- Final `docs/PROGRESS.md` marking Version 1 complete and listing Phase 2 items.
Accept when: `/methodology-audit` returns zero BLOCK, CI is green, and a fresh clone works end to end by following `README.md`.

### After Version 1 (only when I ask)
Action plans with owners, innovation identifier, consultation booking, payments, consultant overrides and notes, industry benchmarks.

## 6. Start now

Do the "Before you do anything" list, reply with the 12-line plan, say "Starting Phase <n>", and go.
