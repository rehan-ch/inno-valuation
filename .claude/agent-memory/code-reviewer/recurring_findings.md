---
name: recurring-findings
description: Issues found in past reviews and accepted architecture decisions; check whether they are still open before re-flagging
metadata:
  type: project
---

Status as of the pre-merge review of phase-1-scoring-engine (2026-10-12):

FIXED (do not re-flag):
- (fixed by 2026-10-13) frontend types now generated (schema.d.ts from openapi.json); ENVIRONMENT now defaults to production; `mypy tests` is clean.
- 500s lose CORS headers: fixed by pure ASGI `UnhandledErrorMiddleware` added before CORSMiddleware, with a test.
- `secret_key` default unguarded: validator now rejects it in staging/production (but see ENVIRONMENT item below).
- CI Node 20: CI now uses 22 (README, `engines`, `@types/node` and the dev box still say 20).
- Float weights and unbounded Decimal weights: weights.py rejects floats, WEIGHT_LIMITS 0..1000, 6 dp.
- YAML `<<:` merge nit: merge keys are now rejected outright.
- tests/scoring/test_readiness.py mypy error: gone. Stale weights docs (PROGRESS, decisions, Q22): fixed.

STILL OPEN (call them repeats if seen again):
- Celery `task_acks_late=True` globally: AI tasks must be idempotent.
- pre-push blocks any push to refs/heads/main, including the first push of main to a new remote. The repo had no git remote on 2026-10-12, so CI has never run.
- commit-msg ATTRIBUTION_PATTERN rejects messages that mention `CLAUDE.md` (nit). User rule: no AI attribution in commits, so the pattern itself is intended.

Phase 2 auth review (commit 48c168c, 2026-10-13), OPEN unless fixed later:
- Pre-account takeover: sign_up on an existing UNVERIFIED email keeps the first (attacker's) password_hash; verify_email then trusts it. Escalates to critical when Google sign-in links by email.
- Throttle race: services/auth.py sign_in reads is_locked unlocked, runs argon2, then record_failure, so parallel requests get far more than 5 guesses.
- Cookies lack `__Host-` prefix in deployed envs (sibling-subdomain cookie tossing = login CSRF).
- Email links put the token in `?token=` (Referer/analytics leak); frontend pages must use no-referrer + replaceState, or a fragment.
- Audit amplification: every sign-in failure (unknown email, and the cheap "locked" path) writes an audit_events row; known-user failures copy the email into details.
- forgot/resend: known email does insert+commit+enqueue, unknown returns at once (timing enumeration).
- current_org / resolve_org_access ignore Organisation.status (archived orgs stay editable).
Accepted in docs/decisions.md (do not re-flag): sign-out clears this browser only (JWT stays valid until exp); per-IP limits and throttle-row pruning deferred to edge/periodic task; SECRET_KEY rotation voids links and sessions.

Phase 2 watch list: map `ScoringError` to an AppError 422 in services (otherwise 500); CSRF/SameSite for the cookie JWT (CORS has allow_credentials); cross-org 404 test fixture; disable /docs in production; question_set.py reads repo-root docs/methodology/dimensions.yml (Docker image must copy it or set INNO_QUESTION_SET_PATH).

Accepted engine decisions: Fraction maths, rounded once with ROUND_HALF_UP (PROVISIONAL Q18). Weights never change any score (Amy Q2(b)); they only break priority ties (PROVISIONAL Q23), then book order (Q19). VfM divides by the rounded IQ. The libyaml CSafeLoader subclass is safe. Raw formula helpers are private.

Accepted decisions (see docs/decisions.md): Celery is eager in tests, so CI has no Redis. Tests use a throwaway DB per run with a rolled-back transaction per test (join_transaction_mode="create_savepoint"). Health returns 200 with database "error" when the DB is down.

**Why:** these let the next review check what was already raised.
**How to apply:** before re-flagging, check whether an item was fixed. If it is still open on a later branch, call it a repeat.

Related: [[review-workflow]]
