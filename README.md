# InnoValuation

Innovation diagnostic platform built on Amy-Renee's "12 Dimensions of Innovation". See `docs/PROGRESS.md` for where the build is, `docs/methodology/` for the scoring rules and `docs/architecture/` for the data model.

## Run it locally

Needs: `uv`, Node 20 with `npm`, Docker with Compose.

```bash
bin/setup        # .env from .env.example, Postgres + Redis in Docker, backend venv, migrations, frontend deps
bin/dev          # API on :8000, Celery worker, Next.js on :3000
```

Then open http://localhost:3000/health (the page calls `GET /api/v1/health`).

Services from `docker-compose.yml`: Postgres on `localhost:5440`, Redis on `localhost:6390`.

## Git hooks

`bin/setup` turns on the hooks in `.githooks/` (`git config core.hooksPath .githooks`). All checks live in `bin/check`, so you can run them by hand too.

| Hook | Runs | Checks |
|---|---|---|
| `pre-commit` | `bin/check staged` (seconds) | no secrets, `.env` files, keys, conflict markers or files over 1 MB; ruff lint and format and mypy on staged Python; eslint with zero warnings on staged TypeScript; scoring tests when the engine or `dimensions.yml` changes |
| `commit-msg` | `bin/check message` | subject is `type(scope): summary`, at most 100 characters; no AI attribution or co-author lines |
| `pre-push` | `bin/check range` + `bin/check full` (about a minute) | no direct push to `main` (except the first push that creates it on a new remote); pushed commits scanned for secrets and attribution; lock file in sync; ruff, mypy, all backend tests (Postgres must be up), migrations match models, OpenAPI types current, frontend lint, typecheck, tests and build; `pip-audit` and `npm audit` on production dependencies |

Do not skip them with `--no-verify`. CI runs the same checks, so a skipped hook only moves the failure to CI.

## Tests and checks

```bash
bin/test-scoring                                   # scoring engine only, no database, under 10 s
cd backend && uv run pytest                        # full backend suite (needs Postgres from docker compose)
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
cd frontend && npm test && npm run lint && npm run typecheck && npm run check:api
```

After changing any API route or schema, regenerate the contract and the frontend types, then commit `frontend/openapi.json` and `frontend/src/lib/api/schema.d.ts`:

```bash
cd backend && uv run python -m app.openapi_dump > ../frontend/openapi.json
cd frontend && npm run gen:api
```

CI fails when either file is stale. Import API types from `frontend/src/lib/api/types.ts`, never hand-write them.

The backend suite creates a throwaway database per run on the `TEST_DATABASE_URL` server and drops it afterwards. Celery runs eagerly in tests. CI (`.github/workflows/ci.yml`) runs all of the above on every pull request and on every push to `main`.
