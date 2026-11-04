# Progress

## Phase and branch
- Phases 0 to 3 are merged to `main` (Phase 2 through PRs 1 and 2, the readiness flow through PR 3, the AI foundation through PR 4, the repository cleanup through PR 5, the whole-codebase review fixes through PR 6, the design refresh through PR 7).
- Work happens on short-lived branches merged through pull requests; the pre-push hook refuses a direct push to `main`. The code is mirrored into Haroon's repository, which starts from one fresh commit; this repository keeps the full history. Personal files (`.claude/`, `CLAUDE.md`, agent notes) are excluded per clone by `bin/setup`; working material (`planning/`, `ask-amy/`, `reference/`, `files3/`, client documents) is in `.gitignore`.

## In progress
Phase 4, ideas and IQ (merged, PR 8; review fixes on branch `phase-4-review`)
- Done (P4.01): tables and reversible migration `0010_ideas`: ideas, IQ assessments, dimension scores; money in minor units with the ISO 4217 exponent table; scores 1 to 10 checked in the database; `ideas.view`, `ideas.create` and `ideas.manage` in the permission matrix (consultants see assessed ideas only).
- Done (P4.02): ideas API and screens: add, edit, archive and restore; title, summary, problem, target market, what makes it different, team, risks, stage; planned investment and expected value with a currency (the organisation's by default); the creator owns the idea, owners and admins manage every idea.
- Done (P4.04): AI touchpoint 3 `propose_iq_scores`: a 1 to 10 score per dimension with 2 to 4 sentences quoting the idea and a confidence, plus open questions about what is missing; strict output (every dimension exactly once, no IQ, total, level, band or value for money); the dimensions, parts and levels verbatim from the question set; the idea's text as escaped data; money never sent; recorded cases typical, sparse, adversarial, adversarial-obeyed and retry; the offline stand-in proposes marked sample scores.
- Done (P4.05, P4.06): the owner's review page: the AI's score and reasons beside a 1 to 10 control and a note per dimension, saved as it goes; confirm runs the engine once (IQ, levels, category IQ, priorities with the book's next steps, Value for Money from the idea's investment) and the assessment is immutable afterwards; scoring again creates a new assessment and keeps the old one.
- Done (P4.07): the ideas list with IQ and cost per innovation point, sort by newest, IQ or Value for Money, a warning when currencies differ, and a compare page (side by side, CSV export). The dashboard shows the ideas at a glance and a "Score your first idea" step; "Ideas" is in the main navigation.
- Done (P4.09): the golden flow as a request test: a recorded proposal whose 12 scores add up to 83, Organizational Agility changed from 4 to 5, IQ 70.0 and Value for Money 714.29 for 50,000; plus immutability, supersession, a failed proposal retried, review rules, money decimals, roles, consultant and cross-organisation isolation. Backend: 1,329 tests; frontend tests, lint, typecheck and build pass.
- Done (P4.08): dimension importance: one weight per dimension per organisation (equal by default, 0 to 1000, at most 6 decimals, checked by the engine), set by owners and admins behind `weights.manage`, every change kept as history with a change-log event naming the dimensions; confirming an idea stores the weights in force and uses them only to order tied priorities (the IQ never changes, proven on the golden proposal); the result page says when custom importance ordered the list; screen `/organisation/importance` with reset to equal and the history. Migration `0011_dimension_weights`.
- Done (P4.10, review): merged into `main` (PR 8). Methodology check 0 BLOCK, 8 WARN; code review 10 findings; all applied with tests (levels only from the engine, prompt version 2, a failed proposal no longer locks the idea, no commits under the idea lock, consultants keyed to confirmed assessments, confirm blocked after a failed save, ISO money decimals on the client, note length 422, compare page loads in parallel). Backend: 1,342 tests; frontend: 151.
- Not built yet: P4.03 (AI context questions about the company; waits on IN.02 and the key, and the proposal prompt has a place for the answers). Still to do for P4.10: Amy tries scoring an idea and checks the reasons.
- Details per decision in `docs/decisions.md` (2026-11-02 to 2026-11-04).

Design refresh (merged, PR 7)
- Done: every screen and shared component moved to a plain, professional system (one sans face, bordered white panels, one action colour, tab navigation, segmented answer control). Nothing about numbers, wording or behaviour changed. Details in `docs/decisions.md` (2026-10-27).
- Still to do by a human: push the mirror to Haroon's repository (see below).

Phase 3 close-out (P3.08)
- Done: code review passed and merged (PR 6). The Trello card's review and merge items are ticked; "Checked against Amy's scoring rules" and "First real demo for Amy" are still open.
- Next: Amy's first demo (a company answers the questions and sees its result). Until the AI key arrives, explanations show marked sample text.
- Haroon's mirror holds one commit cut from the PR 5 merge (25 October) without the internal docs (`PROGRESS.md`, `decisions.md`, `data-model.md`, the book PDF, `ai-touchpoints.md`, `open-questions.md`, `prototype-review.md`). A fresh mirror commit from the PR 8 merge (Phases 3 to 4 and the design refresh) is ready on the local `mirror` branch. Still to do by a human: push it (the pre-push hook refuses pushes to any `main`, so it goes by hand with `--no-verify`), and delete the merged `review-fixes` branch on the remote. Haroon has since pushed an `update-ui` branch to his repository that restyles the sign-in pages and touches the same files; agree which design wins before the push.
- Deploying `main` signs everyone out once (older session tokens carry no session id).

Whole-codebase review fixes (merged, PR 6)
- Done: every finding from the review of Phases 0 to 3 is fixed with a test. Highest first: the secret scan in `bin/check` could miss a key near the top of a large diff (now collected first and covered by `bin/check selftest`, which CI also runs); the sign-in `?next=` guard let control characters through to an off-site redirect; the organisation settings form kept the previous organisation's values after a switch; a readiness assessment could never be finalised once every submitter was deleted. Then the mediums: sign-out revokes the session on the server (`0008_revoked_sessions`), a new reset link no longer voids the old one and sign-in, forgot and resend are limited per client address, the forgot-password email is sent as its own retried task, the AI stale window follows the config and run states are compare-and-set, the end-date error shows inside its modal, and a 401 anywhere sends the person back to sign in. Details per decision in `docs/decisions.md` (2026-10-26).

Phase 3 AI (merged)
- Done: the AI foundation (P3.05) and "What does this mean?" on readiness questions (P3.06). Details per decision in `docs/decisions.md` (2026-10-24).

Phase 3 readiness flow (merged)
- Done: readiness tables and reversible migration `0006_readiness` (P3.01): assessments, per-person responses, consensus with per-question notes, results; answers checked 1 to 5 in the database (strict jsonpath); assessment permissions added to the matrix (`assessments.view` for every role including consultants, `assessments.answer` for owner/admin/member/committee, `assessments.manage` for owner/admin).
- Done: the readiness flow, backend and screens (P3.02 to P3.04). API `/api/v1/readiness`: the question set verbatim from the book; start an assessment (one open per organisation); each person saves their own answers as they go and submits all 60; the facilitator starts consensus, sees every submitted answer with the mean (2 decimals) and spread, sets agreed answers and notes, and finalises; the engine scores the agreed answers only and the result is written once. Screens: `/readiness` (list and start), `/readiness/[id]` (questionnaire with autosave, per-dimension progress, submit; the facilitator's team progress and start consensus), `/readiness/[id]/consensus`, `/readiness/[id]/result` (total out of 300 with the band in the book's words, categories with maximums, the 12 dimensions, priorities with the book's next steps, strengths). The dashboard's readiness card and checklist use the real status.
- Done (P3.07): request tests for the golden flow (three people, agreed total 190, Building Blocks), immutability, missing participants, rounding, permissions and cross-organisation isolation; exercised end to end against the running stack.

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
- `9e450ee` chore(git): ignore local `ask-amy/` drafts.
- `516b6d0` docs(methodology): Amy's answers recorded (Q1, Q2, Q5, Q7, Q9, Q11, Q12, Q16 decided; Q20 follows from Q2; Q23 new).
- Engine follow-up (next commit): weights never change the IQ (Q2). `score_iq` has no weights; weight validation moved to `app/scoring/weights.py` (`validate_weights`, read-only snapshot); priorities take optional weights as a tie-break after score and before book order (Q23). 621 engine tests. Gate: methodology-guardian 0 BLOCK, 0 WARN; code-reviewer "Ready to merge: yes".

## Done, Phase 2 (merged)
- Done: accounts tables and migrations (`0002` to `0005`); email and password sign-up, verification, sign-in, reset and change password; sessions, CSRF, sign-in throttling; roles and permissions; company separation; creating an organisation; team (members, roles, removal, owner rules); invitations (invite, list, cancel, preview, accept); consultant access (grant with end date, change, revoke, accept, switcher).
- Done (screens): shared UI components (`frontend/src/components/ui/`), API client with the CSRF header and typed wrappers per backend router (`frontend/src/lib/api/`), and the pages: sign-up, sign-in, verify email (including choose-a-password links), forgot and reset password, invitation accept, the signed-in shell with the organisation switcher, team (invite, cancel, change role, remove), consultant access (client admin side and the consultant's own page), account, create organisation, and organisation settings (profile and currency). Email-link tokens travel in the URL fragment and the sign-in redirect preserves it. 61 frontend tests; the whole flow (sign-up to consultant grant) exercised by hand against the live API.
- Done (design system, P2.08): design tokens and the documented type and spacing scale in `globals.css`; Table, Modal, Drawer and EmptyState components; a spinner in Loading; skip-to-content link, `aria-current` navigation and `id="main"` landmarks.
- Day 4 review of the screens applied: open-redirect guard on `?next=`, strict-mode-safe reset-password token read, Modal padding clicks, UTC date rendering, functional list state updates, a re-entry guard in `useSubmit`, sign-out failure handling, and client-side guards on the consultant end-date fields.
- Google sign-in: dropped from the MVP (Haroon's call on the P2.02 card); the backend user model keeps the sign-in-method column, so it can be added later without a migration.
- Field-level form validation (email shape, password minimum, organisation name and currency) and the NIST-style password policy: no composition rules, the NCSC common-password list and context words refused with clear messages; minimum 8 characters.
- Still open on P2.07: Amy tries the demo (sign in, invite a team).

## Decided by Amy (2026-10-08)
- Q1 AI proposes IQ scores, the owner confirms or changes them. Q2 weights never change the IQ, only the priority order. Q5 a facilitator sets the agreed answer. Q7 cost is the planned or known investment; procurement VfM is total purchase value / IQ. Q9 category scores. Q11 the AI judges when to suggest a consultation (built with touchpoint 8, Phase 6). Q12 the client admin invites the consultant, with an end date. Q16 the Version 1 feature list. Q20 follows from Q2.
- Team decisions (not sent to Amy, see `docs/decisions.md`): currency USD by default with a per-organisation setting; Q6 one full assessment; Q4 no per-dimension labels in Version 1.

## PROVISIONAL markers in code
- Q8: `backend/app/scoring/targets.py` (per dimension, both scales).
- Q10: `backend/app/ai/touchpoints/explain_question.py` `COMPANY_FIELDS` (only industry, size and country go to the AI provider).
- Q17: `frontend/src/app/globals.css` (the compass blue and emerald as the brand hues, pending Amy's approval; the rest of the design system is settled, see decisions 2026-10-27).
- Q11: `backend/config/ai.yml` (consultation nudge off until touchpoint 8 is built; Q11 itself is decided).
- Q10: `backend/app/ai/touchpoints/propose_iq_scores.py` `IDEA_FIELDS` (the idea's text fields go to the AI provider; the money never does).
- Q23: `backend/app/services/ideas.py` `confirm` (no organisation weights until P4.08; tied IQ priorities go by book order).
- Q18: `backend/app/scoring/_rounding.py` (half up), `vfm.py` (uses the rounded IQ), `categories.py` (category IQ 1 decimal).
- Q19: `backend/app/scoring/priorities.py` (ties in book order).
- Q21: `backend/app/scoring/priorities.py` `PRIORITY_COUNT = 5`.
- Q22: `backend/app/scoring/weights.py` `WEIGHT_LIMITS` (0 to 1000, at most 6 decimals).
- Q23: `backend/app/scoring/priorities.py` (weight breaks ties after score, before book order; IQ list only for now).

## Open questions
- Still OPEN in `docs/methodology/open-questions.md`: Q3, Q4, Q6, Q8, Q10, Q13 to Q15, Q17 to Q19, Q21 to Q23. Q3, Q4 and Q6 are settled informally (see above) and should be closed with `/decision` when convenient.
- Q23 is the only new methodology question for Amy: how weights reorder priorities, and whether readiness priorities use them too. Ask it together with Q19 if needed.

## Known gaps
- `.env.example` has `EMAIL_FROM=InnoValuation <no-reply@example.com>` unquoted. Harmless now (nothing shell-sources `.env`), but it should be quoted. Agents cannot edit `.env.*` (project permission rule), so a human must change it.
- CI has not yet run on GitHub for a pull request from this repository; the `commits` job (secret and message scan) is new.
- The per-address sign-in limit uses the client address the ASGI server reports. Behind a proxy (Phase 8) the server must be told to honour `X-Forwarded-For`, or every visitor shares one address.
- `npm audit`: 5 findings (3 high, 2 moderate) in dev-only lint dependencies (eslint-config-next). Production dependencies have none; the pre-push and CI audits check production only.
- AI test fixtures are hand-written in the model's output format. Replace them with live recordings once the AI key arrives, and try the explain prompt on a few real questions.
- The backend Docker image (Phase 8) must ship `docs/methodology/dimensions.yml` and set `INNO_QUESTION_SET_PATH`, and must ship `backend/config/ai.yml` and `backend/app/ai/prompts/`.
- `app/services/ideas.py` passes `IqResult.iq` (already rounded) to `vfm`, so VfM always uses the IQ the user sees (Q18). Any later caller must do the same.
- The ideas list sorts and compares on the client from the summaries the API returns; with hundreds of ideas per organisation it would need paging and a server-side sort.

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
