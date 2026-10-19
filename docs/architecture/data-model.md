# Data Model

Relational (PostgreSQL). Every client record belongs to exactly one organisation. All times UTC.

## Tenancy and roles
Built in migration `0002_accounts` (`app/models/accounts.py`, `app/models/audit.py`). Primary keys are UUIDs. Enumerations are VARCHAR plus a named CHECK constraint.

- `Organisation` (`organisations`): name, description, industry, country (ISO 3166-1 alpha-2, optional), size_band, revenue_band, founder_names, website, primary_contact_name, primary_contact_email, currency (ISO 4217, default `USD`), status (`active`, `archived`), created_by_user_id, created_at, updated_at. Organisations are archived, not deleted. Until the archive feature exists, an archived organisation is view-only: it cannot be chosen as the active organisation, and every edit permission is refused. Settings (weights, target defaults) arrive with the features that use them. The logo arrives in Phase 7 with file storage.
- `User` (`users`): email (stored trimmed and lowercased, unique), name, password_hash (empty for Google-only users), google_sub (unique), email_verified_at, is_active (a disabled user cannot sign in), is_platform_admin, terms_accepted_at, terms_version, last_login_at, session_version (integer, at least 1; added in `0003_auth`). A user needs at least one sign-in method (password or Google; see Q14). A user is not tied to one organisation: memberships link the two.
- Sessions are not stored. The session is a signed JWT in an httpOnly cookie that carries the user id, the `session_version` it was issued under, the CSRF token and the active organisation id. Raising `users.session_version` (password change, password reset, account disable) ends every existing session at once.
- `SignInThrottle` (`sign_in_throttles`, added in `0003_auth`, columns renamed in `0004_auth_hardening`): key_hash (HMAC-SHA256 hex of the normalised email, unique), attempt_count, window_started_at, locked_until, updated_at. Counts password attempts per email, whether or not an account exists, so a lock never reveals which emails are registered. An attempt is counted under a row lock before the password is checked, so parallel guesses cannot pass the limit. Holds no email and no organisation data. Deleted on a successful sign-in or password reset.
- `Membership` (`memberships`): organisation, user, role. One per (organisation, user). Roles: `owner`, `admin`, `member`, `committee`, `investor` (investor is a role inside one company, PROVISIONAL Q13).
- Platform staff (tech admin, Haroon) are not a membership role. `users.is_platform_admin` marks them, because they span organisations.
- `Invitation` (`invitations`): organisation, email, role, token_hash, invited_by, expires_at, accepted_at, revoked_at. At most one pending (not accepted, not revoked) invitation per (organisation, email): inviting the same email again revokes the old one. A link lasts 7 days. The raw token is an HMAC of the row id under its own key (never the user-token key). Accepting needs a signed-in, verified account with the invited email; someone who is already a member keeps their role.
- `UserToken` (`user_tokens`): user, purpose (`verify_email`, `reset_password`), token_hash, expires_at, used_at, requires_password (boolean, added in `0004_auth_hardening`). Single use. A repeat sign-up for an email whose account is not verified yet never carries a password and never changes the account: its verification link has `requires_password` set, and using it needs a new password in the same request, which replaces whatever password the account had. Once any verification link of an account required a password, every later one does too, until the email is verified. A first sign-up's link stays one click and keeps the password chosen at sign-up. Only `verify_email` tokens may set `requires_password` (CHECK).
- `ConsultantGrant` (`consultant_grants`): organisation, consultant_email, consultant_user (set when the consultant accepts), granted_by, scope (`read_results` for now), expires_at (required), revoked_at, accepted_at. The only way a consultant sees client data. A consultant is never a membership. The client's admin invites the consultant and chooses when access ends (Q12). A grant is active when accepted, not revoked, and `expires_at` is in the future. The consultant accepts while signed in with a verified account for `consultant_email` (no link token; indexed by `consultant_email`, migration `0005_team`). At most one open (not revoked, not ended) grant per (organisation, email); the admin can move the end date earlier or later, or revoke. A member of the organisation cannot also be given consultant access.
- `AuditEvent` (`audit_events`): organisation (empty for events outside an organisation, such as signing in), actor_user, action, target_type, target_id, details (jsonb), created_at. Details never hold secrets, passwords, tokens, idea text, answers or company details. Actions are listed in `AuditAction` (`app/services/audit.py`). A failed sign-in stores the reason, plus the normalised email only when it belongs to an account; an organisation edit stores the changed field names, never the values.

Tokens (invitations, email verification, password reset) are stored only as SHA-256 hex digests. The raw token exists only in the email link.

On delete:
- Organisation: memberships, invitations and consultant grants are deleted with it. Audit events block the delete (RESTRICT).
- User: memberships, user tokens and grants where they are the consultant are deleted. "Created by", "invited by", "granted by" and the audit actor become NULL, so those records stay.

Rule: routers get the organisation from the `current_org` dependency (resolved from the membership, or from an active consultant grant), never from a parameter. `require_role(...)` or `require_permission(...)` on every organisation route. One request test per model proves cross-organisation reads return 404. The role and permission matrix is in [permissions.md](permissions.md).

## Question bank
- `docs/methodology/dimensions.yml` is loaded once by `app.scoring.question_set` into a `QuestionSet` with `version`. Assessments store `question_set_version`. Changing wording bumps the version; old assessments keep theirs.

## Readiness (organisation)
Built in migration `0006_readiness` (`app/models/readiness.py`). Every table carries its own `organisation_id` (indexed), and the database checks every JSONB answer value is a whole number 1 to 5 (strict jsonpath, so arrays and strings fail too). Question ids are checked against the question set in the service layer.

- `ReadinessAssessment`: organisation, question_set_version, status (`draft`, `collecting`, `consensus`, `final`), weights_snapshot, created_by, started_at, finalised_at.
- `ReadinessResponse`: assessment, user, answers (jsonb `{question_id: 1..5}`), submitted_at. One per respondent; deleted with the participant.
- `ReadinessConsensus`: assessment, answers (jsonb), notes (jsonb `{question_id: text}`, the facilitator's reasoning), set_by (NULL when that user is deleted). One per assessment. Provisional, see Q5.
- `ReadinessResult`: assessment, per_dimension (jsonb `{key: score}`), category_scores, total (0..300 checked), band_key, priorities (jsonb), computed_at. One per assessment. Immutable once the assessment is final (enforced in the service layer and by a test).

## IQ (idea)
- `Idea`: organisation, title, summary, problem, target_market, uniqueness, team, risks, investment_minor, currency, expected_value_minor, stage, created_by.
- `IqAssessment`: idea, question_set_version, status (`proposed`, `confirmed`), weights_snapshot, iq, category_scores, priorities, confirmed_by, confirmed_at. Immutable once confirmed. Re-assessment creates a new record.
- `DimensionScore`: iq_assessment, dimension_key, proposed_score, proposed_rationale, proposed_confidence, ai_run_id, final_score, level_key, edited_by.
- `VfmSnapshot`: iq_assessment, investment_minor, currency, vfm_per_point. Nil when IQ is 0.

## AI
- `ContextAnswers`: organisation, questions (jsonb), answers (jsonb), ai_run_id, answered_at. Used by touchpoints 3 to 6.
- `AiRun`: see `docs/methodology/ai-touchpoints.md`. `subject_type` + `subject_id` columns (no ORM polymorphism magic).
- `Recommendation`: subject (ReadinessResult or IqAssessment), dimension_key, fixed_text, ai_json, ai_run_id, priority_rank.
- `Interpretation`: subject, summary, per_dimension (jsonb), ai_run_id.

## Targets, reports, history
- `Target`: organisation, scale (`readiness`, `iq`), scope (`dimension`, `category`, `total`), scope_key, value, set_by. See Q8.
- `Report`: subject, pdf_path (object storage key), snapshot (jsonb of everything rendered), generated_at. The snapshot makes old PDFs reproducible.
- History is the set of final ReadinessResults and confirmed IqAssessments over time. No separate history table.

## Indexes and constraints
- `organisation_id` on every client table, indexed. A full (not partial) composite index or unique constraint that starts with `organisation_id` counts (for example `(organisation_id, user_id)` on memberships). The same applies to every foreign key; `tests/models/test_schema.py` enforces it.
- Every timestamp is `timestamptz` (UTC).
- Unique: `(readiness_assessment_id, user_id)` on responses; `(iq_assessment_id, dimension_key)` on scores.
- Check constraints: answers 1..5, scores 1..10, investment >= 0.
