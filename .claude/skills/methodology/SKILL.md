---
name: methodology
description: Core scoring rules of Amy's 12 Dimensions methodology, condensed. Claude loads this automatically when working on scoring, readiness, IQ, VfM, prompts, dashboards or reports.
user-invocable: false
paths:
  - "backend/app/scoring/**"
  - "backend/app/services/**"
  - "backend/app/ai/**"
  - "backend/app/jobs/**"
  - "backend/app/schemas/**"
  - "backend/app/reports/**"
  - "backend/tests/scoring/**"
  - "docs/methodology/**"
  - "frontend/**/dashboard/**"
  - "frontend/**/assessment/**"
  - "frontend/**/compass/**"
  - "frontend/**/readiness/**"
---

# The method in one page

Two separate report cards plus a price tag. Full detail: docs/methodology/scoring-spec.md. Data: docs/methodology/dimensions.yml.

## Readiness (the organisation)
- 60 questions, 5 per dimension, each answered 1 to 5.
- Dimension = sum of its 5 answers (5 to 25). Total = sum of 12 (60 to 300).
- Bands on the total: 250 to 300 Innovation Champion; 175 to 249 Building Blocks; 100 to 174 Emerging Innovator; below 100 Beginner.
- Several people can answer; the final result uses consensus answers (mechanism PENDING Q5).

## IQ (one idea)
- 12 dimensions, each scored 1 to 10. Levels: 1 to 3 Continuous Improvement, 4 to 6 Innovation, 7 to 10 Invention.
- IQ = sum / 120 x 100, 1 decimal. Example: 84 gives 70.0.
- AI proposes the scores with a rationale; override rule PENDING Q1. Weights equal by default, client editable; weighted formula PENDING Q2.

## Never mix the two
Readiness and IQ are two independent views. Never add, average or blend them.

## VfM
- cost / IQ, in currency per innovation point, 2 decimals, lower is better. Nil when IQ is 0. Example: 50,000 / 70 = 714.29.

## Also required
- Priorities: the 5 lowest dimensions, per assessment.
- Targets and gaps per dimension (granularity PENDING Q8).
- Recommendations = fixed next_steps text from dimensions.yml plus AI additions; every AI item names its dimension.
- Reassessment never overwrites; compare over time on the same question_set_version.

## AI boundary
AI explains, proposes 1 to 10 IQ scores, interprets, suggests. AI never computes totals, bands, priorities, rankings or VfM.

## Not part of the method (never build)
Grades A to E, risk score, novelty or feasibility scores, aspect-count points, readiness tiers Nascent, Developing, Ready, Leading, invented readiness dimensions, hardcoded benchmark numbers.

## Pending rules
Implement only as one named constant with `PROVISIONAL: see open-questions Qn`. See docs/methodology/open-questions.md.
