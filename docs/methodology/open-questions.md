# Open Questions for Amy (and Haroon)

Rules Amy has not decided yet. Each one blocks or shapes code. Keep every question short enough for Amy to answer in one line.

How to use this file:
- Status is OPEN or DECIDED. Only `/decision` changes it.
- "Provisional default" is what the code does meanwhile, always marked `PROVISIONAL: see open-questions Qn`.
- `/ask-amy` turns the OPEN ones into a message for Amy.

---

## Q1 Can a person change the 1 to 10 scores that AI suggests for an idea?
- Status: DECIDED
- Why it matters: decides whether AI scores are final or proposals, and whether we build a review and confirm step.
- Options: (a) AI score is final; (b) AI proposes, the idea owner confirms or edits; (c) a committee confirms.
- Provisional default: (b).
- Affects: IqAssessment status, DimensionScore model, idea assessment page.
- Decision: (b). The AI proposes each 1 to 10 score with a rationale. The idea owner confirms or changes it. The confirmed score is final.
- Decided by / on: Amy, 2026-10-08 (answered questionnaire)

## Q2 When a client changes the dimension weights, how should the IQ be calculated?
- Status: DECIDED
- Why it matters: the book formula (sum / 120 x 100) only works with equal weights.
- Options: (a) weighted average of the 12 scores x 10; (b) weights only change the order of priorities, not the IQ number; (c) other.
- Provisional default: (a).
- Affects: `app/scoring/iq.py`, weights settings page.
- Decision: (b). Weights do not change the IQ. The IQ is always the book formula: sum of the 12 dimension scores / 120 x 100, 1 decimal. Client weights (equal by default, client-editable) only change the order of the priorities list. How they change the order is Q23.
- Decided by / on: Amy, 2026-10-08 (answered questionnaire)

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
- Status: DECIDED
- Why it matters: decides the data model (one submission per person) and the consensus screen.
- Options: (a) average of everyone's answers; (b) everyone answers, then a facilitator sets the final answer per question; (c) everyone answers, then the group re-answers together.
- Provisional default: (b), with the average and spread shown to help.
- Affects: ReadinessResponse, consensus page, result computation.
- Decision: Each respondent answers on their own. A facilitator sees every answer, the mean (2 decimals) and the spread, and sets the agreed answer per question. The final result uses the agreed answers only. Every submission is kept to show how scores evolved. (Option a on Amy's renumbered questionnaire; this matches option b above.)
- Decided by / on: Amy, 2026-10-08 (answered questionnaire)

## Q6 Which assessment types exist, and which questions are mandatory in each?
- Status: OPEN
- Why it matters: Amy said mandatory "depends on the assessment". We need the list of assessment types.
- Options: (a) one full assessment, all 60 required; (b) a short version plus a full version; (c) per-category assessments.
- Provisional default: (a).
- Affects: questionnaire flow, validation, result completeness.
- Decision:
- Decided by / on:

## Q7 For Value for Money, what exactly is "cost"?
- Status: DECIDED
- Why it matters: VfM = cost / IQ. We need to know what number the client enters.
- Options: total planned investment; annual spend; cost to date. Also: which currency, and how VfM works for a procurement opportunity or a whole dimension.
- Provisional default: total planned investment, idea level only, in the organisation's currency.
- Affects: Idea form, `app/scoring/vfm.py`, compare page.
- Decision: For an idea, cost is the total planned or known investment in the idea. For a procurement opportunity, VfM is the total purchase value / IQ, in currency per innovation point. Amy: "total purchase value which is like an investment divided by IQ to get a dollar spend per point of innovation". VfM for a whole dimension is not defined and is out of Version 1. Currency is a product setting, not a methodology rule: USD by default, selectable per organisation.
- Decided by / on: Amy, 2026-10-08 (answered questionnaire)

## Q8 Where can a target score be set?
- Status: OPEN
- Why it matters: decides the targets UI and the gap calculation.
- Options: (a) per dimension; (b) per category; (c) on the total; (d) all of these.
- Provisional default: (a), on both scales.
- Affects: Target model, dimension drill-down, AI gap suggestions.
- Decision:
- Decided by / on:

## Q9 How should the 3 category scores be calculated?
- Status: DECIDED
- Why it matters: Amy wants category totals; the book does not define them.
- Options: readiness: sum of dimension scores (/125, /50, /125) or average (/25); IQ: average of dimension scores x 10 (/100) or sum.
- Provisional default: readiness sum, IQ average x 10.
- Affects: `app/scoring/categories.py`, compass, PDF.
- Decision: Readiness category score is the sum of its dimension scores, shown with the max (Customer-Facing /125, Process /50, Strategic /125). IQ category score is the mean of its dimension scores x 10, out of 100.
- Decided by / on: Amy, 2026-10-08 (answered questionnaire)

## Q10 Which AI provider is acceptable, and may client strategy data be sent to it?
- Status: OPEN
- Why it matters: legal and trust. Also whether a data region (EU, US) is required.
- Options: Anthropic; OpenAI; either; with or without a data-processing agreement.
- Provisional default: Anthropic, no data region constraint.
- Affects: AiClient, privacy policy, hosting.
- Decision:
- Decided by / on:

## Q11 What counts as a "significant gap" that should trigger "book a consultation"?
- Status: DECIDED
- Why it matters: Amy wants the nudge; the threshold is undefined.
- Options: gap of N points on a dimension; total gap of N; any dimension in the lowest band; AI judgement.
- Provisional default: nudge off.
- Affects: touchpoint 8, dashboard banner.
- Decision: AI judgement. There is no fixed number. The AI looks at the gap between where the company is and where it wants to be, and recommends a consultation when it sees a significant gap. Amy: "There is no hard and fast number so let AI recommend".
- Decided by / on: Amy, 2026-10-08 (answered questionnaire)

## Q12 Which user roles are needed in Version 1, and how does a client give Amy access?
- Status: DECIDED
- Why it matters: shapes the whole permission model.
- Options: roles: owner, admin, member, committee member, investor, consultant. Access grant: client admin invites the consultant; consultant requests and client approves; automatic for consulting clients.
- Provisional default: all six roles; client admin grants, with an expiry date.
- Affects: Membership, ConsultantGrant, policies, team page.
- Decision: Roles: client users, organisation admin, consultant (Amy), technical admin (Haroon), committee members, investors. A client's results stay private. The client's admin invites the consultant, and access ends on a date the client chooses.
- Decided by / on: Amy, 2026-10-08 (answered questionnaire)

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
- Status: DECIDED
- Why it matters: Amy ticked "all of the above" but also said action plans, booking, payments and the innovation identifier are "later".
- Options: V1 = login + organisations + readiness assessment + idea IQ assessment + compass + AI interpretation + priorities + VfM + PDF + history. Phase 2 = action plans with owners, innovation identifier, booking, Stripe, consultant overrides.
- Provisional default: the V1 list above.
- Affects: roadmap, every ticket.
- Decision: Version 1: sign-in, company accounts, the readiness questionnaire, idea IQ scoring, the compass, AI explanations, priorities, Value for Money, the PDF report and history. Later: action plans with owners, the innovation identifier, booking and payments, consultant notes or score changes on reports.
- Decided by / on: Amy, 2026-10-08 (answered questionnaire)

## Q17 Brand: colours, fonts, and the final product name spelling.
- Status: OPEN
- Why it matters: Qnr 11.4 was left blank; the prototype changed palette twice. The compass logo exists.
- Options: Amy supplies brand guide; we propose one from the compass mark for approval.
- Provisional default: InnoValuation wordmark + compass mark, neutral palette until approved.
- Affects: design tokens, PDF header, emails.
- Decision:
- Decided by / on:

## Q18 How should IQ and Value for Money be rounded?
- Status: OPEN
- Why it matters: the spec says IQ is rounded to 1 decimal and VfM to 2 decimals. It does not say how to round a half. Round half up works like a calculator. Round half to even is the Python default. It also does not say if VfM divides the cost by the rounded IQ the user sees or by the unrounded IQ. Example: scores that add up to 83 give IQ 69.1666..., shown as 69.2. With a cost of 50,000, VfM is 722.54 using 69.2, or 722.89 using the unrounded IQ. The spec also does not say how many decimals a category IQ shows (Q9 says "mean x 10").
- Options: (a) round half up, VfM uses the rounded IQ shown; (b) round half up, VfM uses the unrounded IQ; (c) other. Category IQ: 1 decimal like the main IQ, or a whole number.
- Provisional default: (a), so a user can recompute every number they see from other numbers they see. Category IQ shows 1 decimal, like the main IQ.
- Affects: `app/scoring/iq.py`, `app/scoring/vfm.py`, `app/scoring/categories.py`, reports.
- Decision:
- Decided by / on:

## Q19 When two dimensions have the same score, which one is the higher priority?
- Status: OPEN
- Why it matters: the priorities list shows the lowest scores first. When two dimensions have the same score, the app needs a fixed rule to pick the order. The spec (section 7) proposes book order, but Amy has not confirmed it.
- Options: (a) book order, the earlier dimension comes first; (b) reverse book order; (c) show all tied dimensions, even if that means more than 5; (d) other.
- Provisional default: (a).
- Affects: `app/scoring/priorities.py`, priorities list, AI touchpoint 5.
- Decision:
- Decided by / on:

## Q20 If a client changes the dimension weights, do the weights also change the category scores?
- Status: DECIDED
- Why it matters: Q2 covers the IQ with weights. Q9 covers category scores. Neither says if weights apply inside a category. The compass and the PDF need one rule.
- Options: (a) no, category IQ is the plain average of its dimension scores x 10; (b) yes, category IQ is the weighted average using the same weights.
- Provisional default: (a).
- Affects: `app/scoring/categories.py`, compass, PDF.
- Decision: (a). Weights change no score at all (Q2), so category scores never use weights.
- Decided by / on: follows from Amy's Q2 answer, 2026-10-08

## Q21 Is the priorities list always 5 dimensions?
- Status: OPEN
- Why it matters: spec section 7 says the app prioritises "normally the lowest 5" dimensions, but does not say when it is not 5. The priorities list, the AI gap suggestions and the PDF all depend on the count.
- Options: (a) always 5; (b) the client chooses the number; (c) 5, plus any dimension tied with the fifth (see Q19).
- Provisional default: (a) always 5.
- Affects: `app/scoring/priorities.py` (`PRIORITY_COUNT`), priorities list, AI touchpoint 5, PDF.
- Decision:
- Decided by / on:

## Q22 What values may a client give the dimension weights?
- Status: OPEN
- Why it matters: Q2 (decided) says weights never change the IQ; they only change the order of the priorities list (Q23). No range is set. Without one, a client could enter a weight like 10 billion, which makes no sense and slows the app down. The weights page also needs to know what to offer. This is a product rule the team decides; it is not being asked of Amy.
- Options: (a) any number from 0 to 1000, any decimals; (b) whole numbers from 0 to 10; (c) percentages from 0 to 100 that must add up to 100; (d) other.
- Provisional default: (a) from 0 to 1000, at most 6 decimal places.
- Affects: `app/scoring/weights.py` (weight validation), weights settings page.
- Decision:
- Decided by / on:

## Q23 How should the client's weights change the order of the priorities list?
- Status: OPEN
- Why it matters: Amy decided weights only change the priority order (Q2), but not how. She answered it for ideas (IQ); it is also not said whether the weights reorder the company's readiness priorities list.
- Options: (a) rank by score as now, and use the weight only to break ties (more important first); (b) rank by a weighted weakness, so an important dimension can come before a slightly weaker but less important one; (c) other. And: the weights reorder (1) the idea (IQ) priorities only, or (2) both the idea and the readiness priorities.
- Provisional default: (a), for the idea (IQ) priorities only. The engine accepts weights for both lists; services pass them to the IQ list only until this is decided.
- Affects: `app/scoring/priorities.py`, priorities list, AI touchpoint 5.
- Decision:
- Decided by / on:
