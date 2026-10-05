# Data Model

Relational (PostgreSQL). Every client record belongs to exactly one organisation. All times UTC.

## Tenancy and roles
- `Organisation`: name, industry, country, size_band, revenue_band, founder_names, currency, settings (weights, targets defaults).
- `User`: email, name, auth provider.
- `Membership`: organisation, user, role. Roles: `owner`, `admin`, `member`, `committee`, `investor` (see Q13), plus `tech_admin` (platform staff).
- `ConsultantGrant`: organisation, consultant_user, granted_by, scope (`read_results`, `add_notes`), expires_at. The only way a consultant sees client data (Qnr 10.6).

Rule: routers get the organisation from the `current_org` dependency (resolved from the membership), never from a parameter. `require_role(...)` on every route. One request test per model proves cross-organisation reads return 404.

## Question bank
- `docs/methodology/dimensions.yml` is loaded once by `app.scoring.question_set` into a `QuestionSet` with `version`. Assessments store `question_set_version`. Changing wording bumps the version; old assessments keep theirs.

## Readiness (organisation)
- `ReadinessAssessment`: organisation, question_set_version, status (`draft`, `collecting`, `consensus`, `final`), weights_snapshot, started_at, finalised_at.
- `ReadinessResponse`: assessment, user, answers (jsonb `{question_id: 1..5}`), submitted_at. One per respondent.
- `ReadinessConsensus`: assessment, answers (jsonb), set_by, set_at. Provisional, see Q5.
- `ReadinessResult`: assessment, per_dimension (jsonb `{key: score}`), category_scores, total, band_key, priorities (jsonb), computed_at. Immutable once the assessment is final (enforced in the service layer and by a test).

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
- `organisation_id` on every client table, indexed.
- Unique: `(readiness_assessment_id, user_id)` on responses; `(iq_assessment_id, dimension_key)` on scores.
- Check constraints: answers 1..5, scores 1..10, investment >= 0.
