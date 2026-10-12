---
name: review-workflow
description: How to get the diff and run checks in this repo as reviewer (permission quirks, which checks run locally)
metadata:
  type: reference
---

- `git diff main...HEAD -- <paths>` with a path list (especially `.env.example`) was denied by permissions on 2026-10-06. `git diff main...HEAD --stat` works; then Read the files directly (the branch is checked out). `.env.example` is denied for both Read and `cat` through Bash, so do not try.
- These all run locally and quickly, so run them instead of guessing: `uv lock --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app`, `uv run mypy tests` (not gated anywhere), `uv run pytest -q` (needs docker-compose Postgres on 5440, usually already up), `uv run alembic check`, and in frontend `npm run lint`, `npm run typecheck`, `npm test`.
- `bin/check range "" HEAD` and `bin/check message <file>` are read-only and safe to run to test the git hook rules.
- To check behaviour (for example CORS on errors), write a short `uv run python -c` script with `ENVIRONMENT=test` and `create_app()`.
- Scratch probe scripts: run from backend with `PYTHONPATH=/home/dev/dev/inno-valuation/backend uv run python <scratch>/probe.py` (`-I` drops the path, so `app` is not found).
- pytest-cov is not installed, so `--cov` fails.
- Timing: `bin/test-scoring` 621 tests in about 2s, full backend 640 tests in about 2s (2026-10-12). Budget is 10s.

Related: [[recurring-findings]]
