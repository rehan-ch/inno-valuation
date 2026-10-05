# InnoValuation

Innovation diagnostic platform. It turns Amy-Renee's "12 Dimensions of Innovation" methodology into a web app: a company answers questions, gets scored, sees a 12-segment compass, gets AI interpretation and recommendations, and downloads a PDF report.

- Methodology owner: Amy (she decides every scoring rule).
- Product owner: Haroon.
- Developer: Ninja.

## Read these first
- `docs/methodology/scoring-spec.md`: the single source of truth for every number the app produces. Read it before touching scoring, prompts, dashboards or reports.
- `docs/methodology/open-questions.md`: rules Amy has not decided yet. Check it before building anything marked PENDING.
- `docs/methodology/dimensions.yml`: the 12 dimensions, their 60 questions, fixed next-step text and sub-aspects. Code loads this file. Never hardcode dimension lists anywhere else.
- `docs/methodology/ai-touchpoints.md`: the 8 places AI is used and what each one may and may not do.
- `docs/architecture/data-model.md`: entities, roles and tenancy rules.

## Non-negotiable rules
1. Amy owns the methodology. Never invent a scoring rule, band, label, weight, threshold or formula. If the spec does not say it, add a question to `open-questions.md` and ask.
2. Two scores, never mixed. Readiness is about the organisation (60 questions, each 1 to 5, total out of 300). IQ is about one idea (12 dimensions, each 1 to 10, IQ = sum / 120 x 100). Never add, average or blend them.
3. AI talks about numbers, it never produces them. All arithmetic lives in the pure scoring engine (`backend/app/scoring/`). The one exception: AI proposes the 1 to 10 IQ dimension scores (touchpoint 3), and those are stored as proposals with a rationale.
4. Every AI output names the dimension it is based on.
5. A PENDING rule may be built only as a provisional default, in one named constant, with the comment `PROVISIONAL: see open-questions Q<n>`. Never silently.
6. Tenant isolation: every query is filtered by `organisation_id`, and the organisation always comes from the `current_org` dependency, never from a request parameter. A consultant (Amy) sees client data only through an explicit grant.
7. Store the prompt, model, raw response and rationale next to every AI result (the `AiRun` table).
8. The Emergent prototype in `reference/prototype/` (if present) is a UX reference only. Never copy its scoring logic, its readiness dimensions, its tier bands or its grades. They are wrong. See `docs/methodology/prototype-review.md`.

## Stack
Backend
- Python 3.12, FastAPI, Pydantic v2. Package manager: `uv`.
- PostgreSQL with SQLAlchemy 2.0 (sync engine, psycopg 3) and Alembic migrations.
- Endpoints are plain `def` (FastAPI runs them in a threadpool). Do not mix in `async def` endpoints that call the database.
- Background jobs: Celery with Redis. Every AI call, PDF render and email send runs in a Celery task.
- Auth: Google sign-in through Authlib plus email and password (argon2). Session is a JWT in an httpOnly cookie.
- Authorisation: FastAPI dependencies in `app/core/deps.py` (`current_user`, `current_org`, `require_role(...)`).
- AI: official `anthropic` Python SDK. Prompts are Jinja2 templates; outputs are validated with Pydantic models.
- PDF: WeasyPrint from Jinja2 HTML templates in `app/reports/templates/`.
- Email: Resend Python SDK.
- Tests: pytest, httpx `TestClient`, factory-boy, a throwaway Postgres database per test run. Lint and types: ruff, mypy.
Frontend
- Next.js (App Router), React, TypeScript, Tailwind, Recharts for the compass. Tests: Vitest + Testing Library.
Hosting: Docker images, Heroku or AWS, Redis add-on.
If any of this changes, update this section and the checklists in `.claude/agents/`.

## Repository layout
```
backend/
  app/
    main.py            FastAPI app, routers mounted under /api/v1
    core/              settings.py, security.py, deps.py (current_user, current_org, require_role)
    db/                session.py, base.py
    models/            SQLAlchemy models, one file per table group
    schemas/           Pydantic request and response models
    api/v1/            routers, thin: validate, authorise, call a service, return a schema
    services/          business logic; the only place that calls scoring and writes results
    scoring/           PURE engine: readiness.py, iq.py, vfm.py, categories.py, priorities.py, targets.py, question_set.py
    ai/                client.py, prompts/<key>.md, schemas/<key>.py, touchpoints/<key>.py
    jobs/              celery_app.py, tasks/
    reports/           templates/, pdf.py
  alembic/
  config/ai.yml        model, max tokens, temperature per touchpoint
  tests/
    scoring/           pure engine tests, fast, no database
    api/               request tests with TestClient
    ai/fixtures/<key>/ recorded AI inputs and outputs
  pyproject.toml
frontend/              Next.js app
docs/                  methodology and architecture
bin/                   setup, dev, test-scoring
```

## Conventions
- `app/scoring/` imports nothing from `app.models`, `app.db`, `app.ai` or `sqlalchemy`. A test enforces this. Inputs and outputs are dataclasses or plain dicts.
- `question_set.py` loads `docs/methodology/dimensions.yml` once at import and exposes `QuestionSet` with `version`, ordered dimensions, bands and levels.
- The question bank is versioned (`question_set_version` column). A reassessment always compares like with like.
- Money is stored as integer minor units plus a 3-letter currency code. Never floats.
- API: JSON under `/api/v1`. Every route declares `response_model`. Errors use `{"error": {"code": "...", "message": "..."}}` through one exception handler.
- Every client table has `organisation_id` with an index. Services take `org: Organisation` as the first argument.
- Alembic: every migration has a working `downgrade()`. Check constraints for 1 to 5 answers and 1 to 10 scores live in the database as well as in Pydantic.
- Celery tasks receive IDs only, re-load the rows, and re-check the organisation.
- `bin/test-scoring` runs only `tests/scoring` and must stay under 10 seconds.
- Commit messages: `type(scope): summary`. Run `/review-pr` before every merge.
- Wording in UI copy and AI text: simple English, short sentences, no em dashes.

## Commands
- `bin/setup`: create the virtualenv with uv, install both apps, create the database, run migrations, seed dimensions.
- `bin/dev`: run FastAPI (`uvicorn --reload`), Celery worker, and Next.js.
- `bin/test-scoring`: engine tests only (the edit hook runs this automatically).
- `cd backend && uv run pytest`: full backend suite. `cd frontend && npm test`: frontend suite.
- `cd backend && uv run ruff check . && uv run mypy app`: lint and types.
- `cd backend && uv run alembic revision --autogenerate -m "..."`, then review the file before committing.

## Definition of done
- The PR description names the spec section it implements.
- Tests written and green, including golden examples when scoring is touched.
- `/spec-check` returns no BLOCK.
- ruff and mypy clean.
- No PENDING rule implemented without a PROVISIONAL marker.
