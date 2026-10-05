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

Accepted decisions (see docs/decisions.md): Celery is eager in tests, so CI has no Redis. Tests use a throwaway DB per run with a rolled-back transaction per test (join_transaction_mode="create_savepoint"). Health returns 200 with database "error" when the DB is down.

**Why:** these let the next review check what was already raised.
**How to apply:** before re-flagging, check whether an item was fixed. If it is still open on a later branch, call it a repeat.

Related: [[review-workflow]]
