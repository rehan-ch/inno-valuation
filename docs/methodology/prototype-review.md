# Review of the Emergent prototype (`innovaluation-complete.zip`)

What it is: a vibe-coded app built on Emergent.sh in about five days. React (CRA) + Tailwind + shadcn, FastAPI + MongoDB, around 6,500 lines. Many screens, lots of features, and several wrong rules.

## Do not copy (wrong against the methodology)
1. IQ rubric. It counts "improved sub-aspects" per dimension (1 = 2 pts, 2 = 5, 3 or more = 10) and an LLM ticks them. The book uses a 1 to 10 maturity scale.
2. Readiness questionnaire. It invents 12 readiness dimensions (Leadership and Vision, Culture and Mindset, Talent and Capability...) and tiers (Nascent, Developing, Ready, Leading). The book uses the same 12 dimensions with 5 questions each and the bands Champion, Building Blocks, Emerging Innovator, Beginner.
3. "Traditional" IQ (novelty, scalability, feasibility, market need), a risk score, and grades A to E. None exist in the method.
4. Hardcoded "typical" benchmark numbers per profile.
5. Six fake demo ideas seeded for every new user.

## Cannot be reused (locked to Emergent)
- Login goes through Emergent's hosted auth server.
- LLM calls go through Emergent's proxy with EMERGENT_LLM_KEY (typesafe-sdk "Jev" and emergentintegrations).
- Email goes through Emergent's Resend wrapper. Crons through `.emergent/crons.yml`.
- Tests only run against the Emergent environment.

## Worth reusing (UX reference only)
- Screen flow: landing, dashboard, submit idea, assessment detail, compare and rank, readiness page, team page, shared portfolio.
- The 12 dimension names, descriptions and sub-aspect lists (they match the book; now in `dimensions.yml`).
- VfM = cost / IQ in currency per point (matches Amy).
- Chart ideas: 12-spoke radar, value quadrant, score history line.
- PDF layout ideas: logo header, score row, radar, per-dimension sections.
- Compass logo assets: `frontend/public/innovaluation_mark.png`, `backend/assets/logo.png`.
- Questionnaire UX: autosave with "Draft saved", resume later, progress per dimension.

If you keep the prototype in the repo, put it under `reference/prototype/` and use the `/prototype` skill to look things up. Never import code from it.
