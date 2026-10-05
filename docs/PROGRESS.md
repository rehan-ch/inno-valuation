# Progress

## Phase and branch
- Phase 0 (Skeleton) complete on `phase-0-skeleton`. Not merged to `main` yet: waiting for Ninja's review. No git remote, so nothing is pushed.
- Next: Phase 1 (Scoring engine) on `phase-1-scoring-engine`, branched from `phase-0-skeleton`.

## Done
- `ace942b` chore(skeleton): backend (FastAPI, settings, sync SQLAlchemy, Alembic baseline, error envelope, Celery ping), frontend (Next 16, `/health`, typed client, Vitest), CI, `bin/setup`, `bin/dev`, docker compose.
- `92e4b5a` fix(dev): `bin/dev` no longer shell-sources `.env`.
- `1ccf7a7` test(scoring): import boundary test resolves relative imports and bans AI, web and job modules.
- `8b10ca9` fix(skeleton): review fixes (CORS on 500s, secret key check, DB connect timeout, localhost-only services, CI hardening, script fixes).

Review: code-reviewer "Ready to merge: yes", no Critical. methodology-guardian: no BLOCK; both WARNs fixed.

## In progress
- Nothing. Next step: start Phase 1 with `question_set.py` loading `docs/methodology/dimensions.yml`.

## PROVISIONAL markers added
- Q11: `backend/config/ai.yml` `consultation_nudge.enabled: false`.

## New open questions
- None.

## Known gaps
- `.env.example` has `EMAIL_FROM=InnoValuation <no-reply@example.com>` unquoted. Harmless now (nothing shell-sources `.env`), but it should be quoted. Agents cannot edit `.env.*` (project permission rule), so a human must change it.
- Frontend API types are hand-written; switch to generated types in Phase 2 (see `docs/decisions.md`).
- CI workflow is written but has never run (no remote).
- `npm audit`: 5 high findings in dev-only lint dependencies (eslint-config-next). Left alone; the fix is a forced breaking upgrade.
- Starlette prints a deprecation warning about `httpx` in the TestClient. Harmless.

## How to run and try it manually
```bash
bin/setup                    # once on a fresh clone
bin/dev                      # API :8000, Celery worker, Next.js :3000
open http://localhost:3000/health
bin/test-scoring             # engine tests, no database
cd backend && uv run pytest  # full suite (needs docker compose services)
cd frontend && npm test
```
