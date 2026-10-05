# InnoValuation Scoring Specification

Single source of truth for every number the app produces. Code implements this file. Nothing else.

**Status legend**
- CONFIRMED: written in the book, or written by Amy in the clarification questionnaire (cited as "Qnr x.y").
- PENDING Qn: Amy has not decided. See `open-questions.md`. Code may use the provisional default only with a `PROVISIONAL: see open-questions Qn` marker.
- PROPOSED: our suggested default, waiting for Amy. Not a decision.

Only the `/decision` skill may change this file (the protect-spec hook enforces it).

---

## 1. The 12 dimensions and 3 categories (CONFIRMED, book + Qnr section 1)

| # | Dimension | Key | Category |
|---|-----------|-----|----------|
| 1 | Customer Journey | `customer_journey` | Customer-Facing |
| 2 | Brand Magnetism | `brand_magnetism` | Customer-Facing |
| 3 | Channel Navigation | `channel_navigation` | Customer-Facing |
| 4 | Service Excellence | `service_excellence` | Customer-Facing |
| 5 | Product Evolution | `product_evolution` | Customer-Facing |
| 6 | Operational Efficiency | `operational_efficiency` | Process |
| 7 | Organizational Agility | `organizational_agility` | Process |
| 8 | Collaborative Synergy | `collaborative_synergy` | Strategic |
| 9 | Value Creation Engine | `value_creation_engine` | Strategic |
| 10 | Sustainable Future | `sustainable_future` | Strategic |
| 11 | Data Intelligence | `data_intelligence` | Strategic |
| 12 | Financial Imperative | `financial_imperative` | Strategic |

Order above is the book order and the display order. Names, questions, next-step text and sub-aspects live in `dimensions.yml` and are loaded, never retyped.

---

## 2. Innovation Readiness (organisation level)

Measures how ready the whole organisation is to innovate. CONFIRMED that readiness is about the organisation, not an idea (Qnr 3.1).

### 2.1 Questions and answer scale (CONFIRMED, book ch. 15; Qnr 4.5)
- 5 questions per dimension, 60 in total, wording verbatim from the book (`dimensions.yml`).
- Each answer is an integer 1 to 5. 1 = Strongly Disagree, 5 = Strongly Agree.

### 2.2 Dimension score (CONFIRMED, book ch. 15)
- `dimension_score = sum of its 5 answers`. Range 5 to 25.

### 2.3 Total score (CONFIRMED, book ch. 15)
- `total = sum of the 12 dimension scores`. Range 60 to 300.

### 2.4 Total bands (CONFIRMED, book ch. 15; Qnr 3.6 "show exactly as written")
| Band | Range | Text shown |
|------|-------|------------|
| Innovation Champion | 250 to 300 | Your organization is thriving in innovation across all dimensions. Maintain momentum and fine-tune strategies. |
| Building Blocks | 175 to 249 | You have a strong foundation but may need to focus on specific weaknesses. |
| Emerging Innovator | 100 to 174 | Significant gaps exist. Prioritize improvements for the lowest-scoring dimensions. |
| Beginner | below 100 | Build innovation capacity step by step, beginning with the foundational dimensions. |

Boundaries are inclusive as written: 249 is Building Blocks, 250 is Innovation Champion, 99 is Beginner, 100 is Emerging Innovator.

### 2.5 Per-dimension status labels (PENDING Q4)
Amy wants labels per dimension (Qnr 3.7: "yes and I like the labels you identified"), but the labels and thresholds Haroon proposed are not in any document we have.
PROPOSED while waiting: none shown. Do not invent thresholds.

### 2.6 Category aggregates (CONFIRMED that they exist, Qnr 5.3; formula PENDING Q9)
PROPOSED: readiness category score = sum of its dimension scores (Customer-Facing out of 125, Process out of 50, Strategic out of 125), shown with the max.

### 2.7 Mandatory questions (PENDING Q6)
Amy: "depends on the assessment" (Qnr 4.4). Which assessment types exist is undecided.
PROPOSED: one assessment type, all 60 questions required to finalise; drafts may be partial.

### 2.8 Multiple respondents and consensus (CONFIRMED that it exists, Qnr 4.2, 4.3; mechanism PENDING Q5)
Amy: multiple people answer; "need to reach a consensus but show evolving scores to get to that consensus".
PROPOSED: each respondent submits their own 60 answers; the app shows the mean per question (2 decimals) and the spread; a facilitator records the final consensus answer per question; the final result is computed from consensus answers only. Every submission is kept so the "evolving" view can be shown.

### 2.9 Save and resume (CONFIRMED, Qnr 4.6)
Drafts are saved automatically and can be resumed.

---

## 3. Innovation Quotient, IQ (idea level)

Measures how innovative one idea or project is. CONFIRMED that IQ is "the main determining factor for each idea" (Qnr 3.1).

### 3.1 Dimension score and levels (CONFIRMED, book ch. 13)
- Each of the 12 dimensions gets an integer 1 to 10.
- Level labels, exactly:
  - 1 to 3: Continuous Improvement
  - 4 to 6: Innovation
  - 7 to 10: Invention

### 3.2 IQ formula (CONFIRMED, book ch. 13)
- `iq = (sum of the 12 dimension scores / 120) x 100`, rounded to 1 decimal. Range 10 to 100.
- Book example: scores summing to 84 give IQ 70.

### 3.3 Who assigns the 1 to 10 scores (CONFIRMED that AI proposes, Qnr 8.1; override PENDING Q1)
Amy: AI should "determine the scoring". Whether a human can change an AI score is undecided.
PROPOSED: AI proposes each score with a rationale; the idea owner confirms or edits; the confirmed score is final. Both the AI proposal and the final value are stored.

### 3.4 Weights (CONFIRMED equal by default and client-editable, Qnr 3.4, 3.5; formula with weights PENDING Q2)
PROPOSED: `iq = weighted mean of the 12 scores x 10`, where weights are non-negative and normalised to sum to 1. With equal weights this equals the book formula. Weights are stored per organisation and snapshotted on each assessment.

### 3.5 Organisation-level IQ (PENDING Q3)
The book (ch. 14) also scores the organisation 1 to 10 per dimension. Amy said IQ is per idea. Whether the organisation itself also gets an IQ, and what "both on the dashboard" shows, is undecided.
PROPOSED: dashboard headline = organisation Readiness (/300) plus the IQ of the selected idea. No organisation IQ until decided.

### 3.6 Category aggregates for IQ (PENDING Q9)
PROPOSED: category IQ = mean of its dimension scores x 10 (out of 100).

---

## 4. Separation rule (CONFIRMED, Qnr 3.3)
Readiness and IQ are "two independent views". They are never added, averaged, blended or converted into each other. Both may be shown side by side (Qnr 3.2 "both on the dashboard").

---

## 5. Value for Money, VfM

### 5.1 Formula (CONFIRMED, Qnr 7.1, 7.2, 7.5)
- `vfm = investment_cost / iq`. Unit: currency per innovation point. Lower is better.
- Undefined (nil) when IQ is 0 or cost is missing. Round to 2 decimals.
- Example: cost 50,000 and IQ 70 gives 714.29 per point.

### 5.2 Where VfM applies (CONFIRMED list, Qnr 7.4; detail PENDING Q7)
Amy: ideas, procurement opportunities, and whole dimensions. What "cost" and "IQ" mean for a single dimension, and the currency and time basis of cost, are undecided.
PROPOSED: idea-level only in Version 1; cost = total planned investment in the idea's currency.

### 5.3 Comparison metric (CONFIRMED, Qnr 7.1)
Ideas are compared on cost per innovation point.

---

## 6. Targets and gaps (CONFIRMED feature, Qnr 5.5; granularity PENDING Q8)
The user sets a target score and sees the gap between current and target, with AI suggestions on how to close it.
PROPOSED: targets per dimension on each scale (readiness target out of 25, IQ target 1 to 10); gap = target minus current.

---

## 7. Priorities (CONFIRMED, Qnr 6.3, 6.4)
- Automatically prioritise the lowest-scoring dimensions. Normally the lowest 5.
- Applies separately to a readiness result and to an IQ assessment.
- PROPOSED tie-break: lower score first, then book order.

---

## 8. Recommendations (CONFIRMED, Qnr 6.1, 6.2)
- Source: a combination of fixed methodology text and AI.
- Fixed part: the "Next Steps" sentence per dimension from book ch. 15 (`dimensions.yml`). Shown as written.
- AI part: interpretation, recommended next steps, priority, suggested initiatives, KPIs, timeline, resources.
- Every AI recommendation cites the dimension it is based on (Qnr 8.3).
- AI asks context questions about the organisation before recommending (Qnr 8.4).

---

## 9. Reassessment and history (CONFIRMED, Qnr 6.6)
A new assessment never overwrites an old one. The app compares results over time per dimension and shows improvement or decline. Comparisons use the same `question_set_version`.

---

## 10. Consultation nudge (CONFIRMED feature, Qnr 10.11; threshold PENDING Q11)
AI recommends booking a consultation "if they have significant gaps in where they are and where they want to be". "Significant" is undefined.
PROPOSED: off until defined.

---

## 11. Golden examples (every one of these is a unit test)

Readiness
- Answers 4, 3, 5, 4, 4 for Customer Journey give dimension score 20.
- All answers 5 give total 300, band Innovation Champion.
- All answers 1 give total 60, band Beginner.
- Totals 99 Beginner, 100 Emerging Innovator, 174 Emerging Innovator, 175 Building Blocks, 249 Building Blocks, 250 Innovation Champion.
- An answer of 0 or 6 is invalid. A missing answer makes the result "incomplete", not 0.

IQ
- Dimension scores summing to 84 give IQ 70.0 (book example).
- All 10s give IQ 100.0. All 1s give IQ 10.0.
- Level: 3 is Continuous Improvement, 4 is Innovation, 6 is Innovation, 7 is Invention, 10 is Invention.
- A score of 0 or 11 is invalid.
- Equal weights reproduce the book formula exactly.

VfM
- Cost 50,000 and IQ 70 give 714.29.
- Cost 300,000 and IQ 84 give 3,571.43.
- IQ 0 gives nil. Missing cost gives nil.

Priorities
- Readiness dimension scores [25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14] in book order give priorities: dimensions 12, 11, 10, 9, 8.

---

## 12. Explicitly NOT part of the methodology (never build these)
These came from the Emergent prototype and are not Amy's method:
- A "Traditional" IQ made of novelty, scalability, feasibility and market need.
- A risk score, or a "risk control" input to any formula.
- Grades A to E.
- The aspect-count rubric (1 improved aspect = 2 points, 2 = 5, 3 or more = 10).
- Readiness tiers named Nascent, Developing, Ready, Leading.
- Readiness dimensions such as Leadership and Vision, Culture and Mindset, Talent and Capability.
- Hardcoded "typical" benchmark numbers per profile.
