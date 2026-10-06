# Progress

## Phase and branch
- Phase 0 (Skeleton) complete on `phase-0-skeleton`, including the git hooks.
- Phase 1 (Scoring engine) complete on `phase-1-scoring-engine`, branched from `phase-0-skeleton`.
- Neither is merged to `main` yet: waiting for Ninja's review. Merging `phase-1-scoring-engine` brings in both. No git remote, so nothing is pushed.
- Next: Phase 2 (Accounts, organisations and roles) on `phase-2-accounts`.

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

## In progress
- Nothing. Next step: Phase 2, starting with the `organisations`, `users` and `memberships` tables and the auth dependencies.

## PROVISIONAL markers added
- Q2: `backend/app/scoring/iq.py` (weighted IQ).
- Q7: `backend/app/scoring/vfm.py` (idea level only, total planned investment).
- Q8: `backend/app/scoring/targets.py` (per dimension, both scales).
- Q9: `backend/app/scoring/categories.py` (readiness sum, IQ mean x 10).
- Q11: `backend/config/ai.yml` (consultation nudge off).
- Q18: `backend/app/scoring/_rounding.py` (half up), `vfm.py` (uses the rounded IQ), `categories.py` (category IQ 1 decimal).
- Q19: `backend/app/scoring/priorities.py` (ties in book order).
- Q20: `backend/app/scoring/categories.py` (weights do not apply inside a category).
- Q21: `backend/app/scoring/priorities.py` `PRIORITY_COUNT = 5`.
- Q22: `backend/app/scoring/iq.py` `WEIGHT_LIMITS` (0 to 1000, at most 6 decimals).

## New open questions
- Q18: rounding mode, whether VfM uses the rounded IQ, category IQ decimals.
- Q19: priority tie-break.
- Q20: whether custom weights change category scores.
- Q21: whether the priorities list is always 5 dimensions.
- Q22: the allowed range for dimension weights.
- `scoring-spec.md` has no PENDING lines for Q18 to Q22 yet. It can only change through `/decision`; add them when Amy answers.

## Known gaps
- `.env.example` has `EMAIL_FROM=InnoValuation <no-reply@example.com>` unquoted. Harmless now (nothing shell-sources `.env`), but it should be quoted. Agents cannot edit `.env.*` (project permission rule), so a human must change it.
- Frontend API types are hand-written; switch to generated types in Phase 2 (see `docs/decisions.md`).
- CI workflow is written but has never run (no remote).
- `npm audit`: 5 high findings in dev-only lint dependencies (eslint-config-next). Production dependencies have none; the pre-push and CI audits check production only.
- Starlette prints a deprecation warning about `httpx` in the TestClient. Harmless.
- The backend Docker image (Phase 8) must ship `docs/methodology/dimensions.yml` and set `INNO_QUESTION_SET_PATH`.
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
