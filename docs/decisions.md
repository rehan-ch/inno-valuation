# Decisions

Engineering decisions inside the stack. One line each: date, decision, reason. Methodology decisions go through `/decision`, not here.

- 2026-10-06: Local Postgres on host port 5440 and Redis on 6390 in `docker-compose.yml`. Avoids clashing with common local services on 5432 and 6379/6380.
- 2026-10-06: Tests create a throwaway database `innovaluation_test_<random>` on `TEST_DATABASE_URL`'s server, migrate it with Alembic, and drop it after the run. Each test runs in a rolled-back transaction. Matches CLAUDE.md "throwaway Postgres database per test run".
- 2026-10-06: `tests/scoring` never touches the database fixtures, so `bin/test-scoring` runs without Postgres and stays fast.
- 2026-10-06: Errors use one `AppError(code, message, status_code)` class; HTTP, validation and unhandled errors map into the same `{"error": {...}}` envelope in one module.
- 2026-10-06: SQLAlchemy metadata uses a constraint naming convention so Alembic names stay stable across autogenerate runs.
- 2026-10-06: `config/ai.yml` defaults to `claude-sonnet-5-5`, with `claude-opus-5-5` for `propose_iq_scores` and `report_narrative` (the highest-stakes outputs). Tunable per touchpoint without code changes.
- 2026-10-06: CI is GitHub Actions with two jobs (backend: ruff, format, mypy, scoring tests, pytest with a Postgres service; frontend: lint, typecheck, vitest, build). Redis is not needed in CI because Celery runs eagerly in tests.
- 2026-10-06: Frontend on Next 16 + React 19 + Tailwind 4 + Vitest 4; `engines.node >= 20.19` because Vite 8 and jsdom 29 need it.
- 2026-10-06: `npm run typecheck` runs `next typegen` before `tsc --noEmit`, since Next 16 route types are generated.
- 2026-10-06: Keep `frontend/AGENTS.md` and `frontend/CLAUDE.md` from create-next-app; `next dev` re-creates them, and they warn agents that Next 16 differs from older docs.
- 2026-10-06: Validation error responses strip submitted `input` and `ctx`, so user text never echoes into responses or logs.
