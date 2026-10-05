# Open Questions for Amy (and Haroon)

Rules Amy has not decided yet. Each one blocks or shapes code. Keep every question short enough for Amy to answer in one line.

How to use this file:
- Status is OPEN or DECIDED. Only `/decision` changes it.
- "Provisional default" is what the code does meanwhile, always marked `PROVISIONAL: see open-questions Qn`.
- `/ask-amy` turns the OPEN ones into a message for Amy.

---

## Q1 Can a person change the 1 to 10 scores that AI suggests for an idea?
- Status: OPEN
- Why it matters: decides whether AI scores are final or proposals, and whether we build a review and confirm step.
- Options: (a) AI score is final; (b) AI proposes, the idea owner confirms or edits; (c) a committee confirms.
- Provisional default: (b).
- Affects: IqAssessment status, DimensionScore model, idea assessment page.
- Decision:
- Decided by / on:

## Q2 When a client changes the dimension weights, how should the IQ be calculated?
- Status: OPEN
- Why it matters: the book formula (sum / 120 x 100) only works with equal weights.
- Options: (a) weighted average of the 12 scores x 10; (b) weights only change the order of priorities, not the IQ number; (c) other.
- Provisional default: (a).
- Affects: `app/scoring/iq.py`, weights settings page.
- Decision:
- Decided by / on:

## Q3 Does the organisation itself get an IQ, or only ideas?
- Status: OPEN
- Why it matters: the book has an organisation-level 1 to 10 table (ch. 14), but Amy said IQ is per idea. "Both on the dashboard" needs a definition.
- Options: (a) only ideas have an IQ; dashboard shows Readiness plus the selected idea's IQ; (b) the organisation also gets an IQ from its own 12 scores; (c) the organisation IQ is the average of its ideas.
- Provisional default: (a).
- Affects: dashboard headline cards, data model.
- Decision:
- Decided by / on:

## Q4 What are the per-dimension status labels and their thresholds?
- Status: OPEN
- Why it matters: Amy said "I like the labels you identified" but those labels are not in any document we have. Needed for the compass colours and dimension cards.
- Options: Haroon to send the labels and thresholds he proposed, for Amy to confirm.
- Provisional default: no per-dimension label shown.
- Affects: dimensions.yml (new section), compass, dimension drill-down, PDF.
- Decision:
- Decided by / on:

## Q5 When several people from one company answer the readiness questions, how do we reach the final answer?
- Status: OPEN
- Why it matters: decides the data model (one submission per person) and the consensus screen.
- Options: (a) average of everyone's answers; (b) everyone answers, then a facilitator sets the final answer per question; (c) everyone answers, then the group re-answers together.
- Provisional default: (b), with the average and spread shown to help.
- Affects: ReadinessResponse, consensus page, result computation.
- Decision:
- Decided by / on:

## Q6 Which assessment types exist, and which questions are mandatory in each?
- Status: OPEN
- Why it matters: Amy said mandatory "depends on the assessment". We need the list of assessment types.
- Options: (a) one full assessment, all 60 required; (b) a short version plus a full version; (c) per-category assessments.
- Provisional default: (a).
- Affects: questionnaire flow, validation, result completeness.
- Decision:
- Decided by / on:

## Q7 For Value for Money, what exactly is "cost"?
- Status: OPEN
- Why it matters: VfM = cost / IQ. We need to know what number the client enters.
- Options: total planned investment; annual spend; cost to date. Also: which currency, and how VfM works for a procurement opportunity or a whole dimension.
- Provisional default: total planned investment, idea level only, in the organisation's currency.
- Affects: Idea form, `app/scoring/vfm.py`, compare page.
- Decision:
- Decided by / on:

## Q8 Where can a target score be set?
- Status: OPEN
- Why it matters: decides the targets UI and the gap calculation.
- Options: (a) per dimension; (b) per category; (c) on the total; (d) all of these.
- Provisional default: (a), on both scales.
- Affects: Target model, dimension drill-down, AI gap suggestions.
- Decision:
- Decided by / on:

## Q9 How should the 3 category scores be calculated?
- Status: OPEN
- Why it matters: Amy wants category totals; the book does not define them.
- Options: readiness: sum of dimension scores (/125, /50, /125) or average (/25); IQ: average of dimension scores x 10 (/100) or sum.
- Provisional default: readiness sum, IQ average x 10.
- Affects: `app/scoring/categories.py`, compass, PDF.
- Decision:
- Decided by / on:

## Q10 Which AI provider is acceptable, and may client strategy data be sent to it?
- Status: OPEN
- Why it matters: legal and trust. Also whether a data region (EU, US) is required.
- Options: Anthropic; OpenAI; either; with or without a data-processing agreement.
- Provisional default: Anthropic, no data region constraint.
- Affects: AiClient, privacy policy, hosting.
- Decision:
- Decided by / on:

## Q11 What counts as a "significant gap" that should trigger "book a consultation"?
- Status: OPEN
- Why it matters: Amy wants the nudge; the threshold is undefined.
- Options: gap of N points on a dimension; total gap of N; any dimension in the lowest band; AI judgement.
- Provisional default: nudge off.
- Affects: touchpoint 8, dashboard banner.
- Decision:
- Decided by / on:

## Q12 Which user roles are needed in Version 1, and how does a client give Amy access?
- Status: OPEN
- Why it matters: shapes the whole permission model.
- Options: roles: owner, admin, member, committee member, investor, consultant. Access grant: client admin invites the consultant; consultant requests and client approves; automatic for consulting clients.
- Provisional default: all six roles; client admin grants, with an expiry date.
- Affects: Membership, ConsultantGrant, policies, team page.
- Decision:
- Decided by / on:

## Q13 Does an investor see one company or many companies?
- Status: OPEN
- Why it matters: if many, the data model needs an investor workspace that spans organisations.
- Options: (a) an investor is just a role inside one company's account; (b) investors have their own workspace and companies share results with them.
- Provisional default: (a).
- Affects: tenancy model, sharing.
- Decision:
- Decided by / on:

## Q14 Login: Google only, or email and password too?
- Status: OPEN
- Why it matters: auth setup and enterprise clients who block Google login.
- Options: Google only; email + password; both; SSO later.
- Provisional default: both.
- Affects: auth settings and Authlib config, landing page.
- Decision:
- Decided by / on:

## Q15 Where does industry benchmark data come from on day one?
- Status: OPEN
- Why it matters: Amy wants benchmarking against industry standards; no data exists yet.
- Options: (a) none in Version 1; (b) aggregated, anonymised platform data once enough exists; (c) Amy supplies reference numbers.
- Provisional default: (a), "not enough data yet" message.
- Affects: benchmark feature, analytics.
- Decision:
- Decided by / on:

## Q16 What is the signed-off Version 1 feature list?
- Status: OPEN
- Why it matters: Amy ticked "all of the above" but also said action plans, booking, payments and the innovation identifier are "later".
- Options: V1 = login + organisations + readiness assessment + idea IQ assessment + compass + AI interpretation + priorities + VfM + PDF + history. Phase 2 = action plans with owners, innovation identifier, booking, Stripe, consultant overrides.
- Provisional default: the V1 list above.
- Affects: roadmap, every ticket.
- Decision:
- Decided by / on:

## Q17 Brand: colours, fonts, and the final product name spelling.
- Status: OPEN
- Why it matters: Qnr 11.4 was left blank; the prototype changed palette twice. The compass logo exists.
- Options: Amy supplies brand guide; we propose one from the compass mark for approval.
- Provisional default: InnoValuation wordmark + compass mark, neutral palette until approved.
- Affects: design tokens, PDF header, emails.
- Decision:
- Decided by / on:
