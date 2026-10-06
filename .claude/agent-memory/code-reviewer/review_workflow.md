---
name: review-workflow
description: How to get the diff and run checks in this repo as reviewer (permission quirks, which checks run locally)
metadata:
  type: reference
---

- `git diff main...HEAD -- <paths>` with a path list (especially `.env.example`) was denied by permissions on 2026-10-06. `git diff main...HEAD --stat` works; then Read the files directly (the branch is checked out). `.env.example` itself is in a denied directory for Read.
- These all run locally and quickly, so run them instead of guessing: `uv lock --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app`, `uv run pytest -q` (needs docker-compose Postgres on 5440), and in frontend `npm run lint`, `npm run typecheck`, `npm test`.
- To check behaviour (for example CORS on errors), write a short `uv run python -c` script with `ENVIRONMENT=test` and `create_app()`.

- Scratch probe scripts: run from backend with `PYTHONPATH=/home/dev/dev/inno-valuation/backend uv run python <scratch>/probe.py` (`-I` drops the path, so `app` is not found).
- pytest-cov is not installed, so `--cov` fails. CI runs `mypy app` only, so type errors in tests are not gated. Run `uv run mypy tests/scoring` by hand.
- `bin/test-scoring` ran in about 3s with 504 tests on 2026-10-06. The budget is 10s.

Related: [[recurring-findings]]
