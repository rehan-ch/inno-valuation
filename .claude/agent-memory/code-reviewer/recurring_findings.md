---
name: recurring-findings
description: Issues found in past reviews and accepted architecture decisions; check whether they are still open before re-flagging
metadata:
  type: project
---

Phase 0 skeleton review (2026-10-06). Open items at the time:
- 500 responses have no CORS headers. The `Exception` handler runs in Starlette's ServerErrorMiddleware, which sits outside CORSMiddleware. I verified this with a script. The browser sees a network error instead of the envelope. Fix: pure ASGI middleware, or add CORS headers in the 500 handler.
- `secret_key` default "change-me-in-production" is not guarded in staging or production.
- Frontend `src/lib/api/types.ts` is hand-written. The checklist requires types generated from OpenAPI (openapi-typescript).
- CI uses Node "20". Node 20 is EOL (April 2026).
- Celery `task_acks_late=True` is set globally, so AI tasks must be idempotent or they can be redelivered (Redis visibility timeout).

Phase 1 scoring engine review (2026-10-06, uncommitted on phase-1-scoring-engine). Open items:
- iq.py `_validated_weights` turns float weights into Fraction(float), which is the exact binary value. 902 of 200k random weight sets rounded differently from the decimal intent, and stored weights look like Decimal('0.1000000000000000055...'). Fix: reject floats, or convert with Decimal(repr(v)).
- Decimal weights have no upper bound. A weight of 1E10000000 took 12s (CPU DoS once weights come from the API). Fix: bound the exponent and size in the engine and in the Pydantic schema.
- The YAML duplicate check runs after flatten_mapping, so a legitimate `<<:` merge override is reported as "Duplicate key". The real file has no merges, so this is a nit.
- tests/scoring/test_readiness.py:134 fails mypy (an int key). It is not gated because CI runs `mypy app` only.

Accepted engine decisions: Fraction maths, rounded once with ROUND_HALF_UP (PROVISIONAL Q18). VfM divides by the rounded IQ. The libyaml CSafeLoader subclass is safe (SafeConstructor, and add_constructor copies the dict on the subclass). Raw formula helpers are private.

Accepted decisions (see docs/decisions.md): Celery is eager in tests, so CI has no Redis. Tests use a throwaway DB per run with a rolled-back transaction per test (join_transaction_mode="create_savepoint"). Health returns 200 with database "error" when the DB is down.

**Why:** these let the next review check what was already raised.
**How to apply:** before re-flagging, check whether an item was fixed. If it is still open on a later branch, call it a repeat.

Related: [[review-workflow]]
