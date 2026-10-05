# InnoValuation: Claude Code setup (FastAPI backend)

Drop-in `.claude/` configuration plus the methodology documents for building InnoValuation with Claude Code. Backend is Python and FastAPI, frontend is Next.js. Everything here was written from the book, Amy's questionnaire answers and a review of the Emergent prototype.

## Install (2 minutes)

1. Create the new repository (do not build on the Emergent prototype).
2. Copy everything in this folder into the repository root. You get:
   ```
   CLAUDE.md                      project memory: rules, stack, layout, conventions
   .claude/settings.json          permissions + hooks
   .claude/hooks/                 protect-spec.sh, scoring-tests.sh
   .claude/agents/                8 subagents
   .claude/skills/                8 skills (slash commands)
   .claude/workflows/             2 dynamic workflow scripts (optional)
   docs/methodology/              scoring-spec.md, dimensions.yml, open-questions.md, ai-touchpoints.md, prototype-review.md
   docs/architecture/data-model.md
   bin/test-scoring               fast engine tests (works once backend/tests/scoring exists)
   ```
3. Install `uv` (Python package manager) and `jq` (the hooks use it; they fall back to grep without it).
4. Optional: unzip the Emergent prototype into `reference/prototype/` and the book text into `reference/book.txt` (`pdftotext -layout 12_Dimensions_of_Innovation.pdf reference/book.txt`). Add `reference/` to `.gitignore` if you do not want it in the repo.
5. Start `claude` in the repository root and accept the workspace trust prompt (needed for the hooks).
6. Run `claude plugin validate .claude/agents` and `claude plugin validate .claude/skills` to confirm every file loads.
7. Read the Stack section in `CLAUDE.md`. It fixes the choices the agents follow (sync SQLAlchemy, Celery, Authlib, WeasyPrint, uv). Change it there if you prefer something else and the agents will follow.

## Who owns which folder

| Folder | Owner agent | Notes |
|--------|-------------|-------|
| `backend/app/scoring/`, `backend/tests/scoring/` | `scoring-engine-dev` | Pure Python. No database, no AI, no HTTP. |
| `backend/app/models/`, `schemas/`, `api/`, `services/`, `jobs/`, `reports/`, `alembic/` | `fastapi-dev` | Everything server-side except the engine and prompts. |
| `backend/app/ai/`, `backend/config/ai.yml`, `backend/tests/ai/` | `ai-prompt-engineer` | Prompts, Pydantic output models, touchpoint runners, fixtures. |
| `frontend/` | `frontend-dev` | Displays numbers, never computes them. |
| `docs/methodology/` | `spec-keeper` | Only through `/decision`. The hook blocks everyone else. |
| Any file | `methodology-guardian`, `code-reviewer`, `test-runner` | Read-only reviewers and runner. |

## What each agent does

| Agent | Job | Edits code? |
|-------|-----|-------------|
| `methodology-guardian` | Checks code, prompts and screens against the scoring spec. Flags invented rules, mixed scores, AI doing math. | No |
| `scoring-engine-dev` | Builds the pure scoring functions and their pytest tests. | Yes |
| `fastapi-dev` | Models, Alembic migrations, routers, dependencies, services, Celery tasks, PDF, email. Enforces tenancy. | Yes |
| `frontend-dev` | Next.js screens, compass, questionnaire, dashboard. | Yes |
| `ai-prompt-engineer` | The 8 AI touchpoints: Jinja2 prompts, Pydantic schemas, tasks, fixtures. | Yes |
| `test-runner` | Runs pytest and Vitest, reports only failures. Cheap model. | No |
| `code-reviewer` | Security, tenancy, sync discipline, migrations, tests. Remembers past issues. | No |
| `spec-keeper` | Updates the methodology docs when Amy decides something. Drafts questions for her. | Docs only |

Claude picks them automatically from their descriptions. To force one, mention it: "use the scoring-engine-dev agent to build app/scoring/readiness.py" or @-mention it.

## What each skill does (type `/name`)

| Skill | Use it when |
|-------|-------------|
| `/kickoff [phase]` | Start of every session. Reads the docs and `docs/PROGRESS.md`, plans the phase, then runs it. `/kickoff 3` jumps to Phase 3, `/kickoff continue` moves on. |
| `/new-feature <name>` | Starting any feature. Runs the full pipeline: spec, open questions, plan, implement, test, spec-check, review, summary. |
| `/spec-check [files]` | After changing anything that produces or shows a number. Runs methodology-guardian. |
| `/review-pr` | Before every merge. Code review + methodology check + tests, one verdict. |
| `/ai-touchpoint <n>` | Building one of the 8 AI features. |
| `/decision Q3 "only ideas get an IQ" by Amy` | Amy or Haroon decided something. Updates the docs and lists the code to change. The only way to edit the signed-off files. |
| `/ask-amy` | You need the current open questions as a message for Amy. |
| `/prototype <screen>` | You want to see how the Emergent app built a screen. UX only; it refuses to report scoring logic. |
| `methodology` | Not typed. Loads itself when you work on scoring, AI, service or dashboard files. |

## The two hooks

- `protect-spec.sh` (before every edit): blocks edits to `scoring-spec.md` and `dimensions.yml` unless `/decision` is running. This is how "no scoring rule gets invented in code" is enforced, not just hoped for.
- `scoring-tests.sh` (after every edit): if a file under `backend/app/scoring/` or `backend/tests/scoring/` changed, runs `bin/test-scoring` and feeds failures straight back to Claude.

## The two workflows (optional)

Need "Dynamic workflows" enabled (paid plans; on Pro, turn it on in `/config`).

- `/methodology-audit`: one agent per scoring-related file, then a verifier. Run it before a release or after a big refactor.
- `/dimension-content-check`: 12 agents compare `dimensions.yml` with the book text. Run it once now, and after any change to the questions.

To edit them, run `/workflow-authoring` first so Claude loads the script reference.

## Suggested first week

The simplest path: type `/kickoff` in every session and let it work phase by phase (the full plan is in `.claude/skills/kickoff/SKILL.md`). If you prefer to drive by hand:

1. `/ask-amy`. Send the message to Amy and Haroon. Q1, Q2, Q4, Q5, Q16 are the ones that block code.
2. `/dimension-content-check` (or ask the methodology-guardian to compare `dimensions.yml` with the book by hand). Confirm the 60 questions are exact.
3. `/new-feature project skeleton`: `uv init` in `backend/`, FastAPI app, settings, Postgres and Redis via docker compose, Alembic, Celery, pytest with a throwaway database, `bin/setup` and `bin/dev`. No business logic yet.
4. `/new-feature scoring engine`. Builds `app/scoring/*` from the spec with the golden tests and the import-boundary test. Zero AI, zero database. This is the foundation.
5. `/new-feature organisations, users, roles and login`.
6. `/new-feature readiness questionnaire with autosave and resume`.
7. As answers come back from Amy: `/decision Qn "..." by Amy`, then fix the listed PROVISIONAL spots.
8. Only then: `/new-feature idea submission`, `/ai-touchpoint 2`, `/ai-touchpoint 3`, dashboard and compass.

## Keeping it honest

- Every number in the app traces to a section of `scoring-spec.md`.
- Every AI sentence traces to an `AiRun` row and names its dimension.
- Every undecided rule is a `PROVISIONAL` constant with a Q number, never a silent guess.
