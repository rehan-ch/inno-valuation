# Demo walk-through

A 15 minute tour of what is built through Phase 5, on the local stack with the demo company.

## Before the demo

```bash
bin/dev                 # API :8000, worker, web :3000 (leave it running)
bin/seed-demo --reset   # a fresh Northwind Outfitters; prints the accounts (needs ENVIRONMENT=development in .env)
```

Open http://localhost:3000/sign-in. Every demo account uses the password the seed prints.

| Person | Role | Use it to show |
|---|---|---|
| dana@northwind.example | Owner | Everything: dashboard, targets, importance, activity log |
| priya@northwind.example | Member | A member's view; she owns "Gear rental subscription" |
| ines@northwind.example | Investor | Read-only: sees results, cannot answer or add ideas |
| amy@consultant.example | Consultant | Amy's view: final results and confirmed ideas only |

Things to know before you start:
- There is no AI key yet. Idea proposals are sample scores (every dimension at the middle of the scale) and the AI's reasons are placeholder text, both marked as sample on screen. The demo ideas were given realistic scores through the owner's review, which is the real flow.
- Signing in more than 30 times in 15 minutes from one machine locks sign-in for that machine. `bin/seed-demo` clears the lock.
- Four things on screen are working defaults that Amy has not confirmed yet, so present them as open, not as her rule: the priorities list shows the lowest five; dimension importance only orders priorities whose scores tie; a target is set per dimension, and an idea target applies to every idea; "strengths" are our own display choice (up to three dimensions above every priority).
- A browser extension can make the development overlay show "1 issue" (a hydration notice). It is not from the app.

## The tour

1. **Dashboard** (sign in as Dana). Two headline scores side by side, never combined: Innovation Readiness 194 out of 300, "Building Blocks", in the book's words; and the Innovation Quotient of one idea out of 100 with its Value for Money. Pick another idea in the card to change the right-hand score only.
2. **Compass.** Below the cards: 12 segments in the book's order, grouped into the three categories with category scores. Hover or tab through the segments; the table beside it holds the same numbers. Dashed marks are targets. Switch between "Readiness" and "Idea IQ": the idea compass is coloured by the book's three levels.
3. **Priorities.** The five lowest dimensions with the book's next steps, separately for readiness and for the idea.
4. **A dimension.** Click "Sustainable Future" (the top readiness priority). The page shows the book's description and next steps, the team's agreed answer to each of its five questions, the idea's score with the AI's reasons and the owner's note, the target and gap on each scale, and how the score moved since the first assessment.
5. **Targets** (top navigation). Set a readiness target for Brand Magnetism, save, and the gap appears. Earlier targets stay in the list below. A target never changes a score.
6. **History.** Readiness went from 165 (Emerging Innovator) to 194 (Building Blocks) in two months, with the change per dimension. Below, "Gear rental subscription" was scored twice: IQ 58.3, then 65.8 after the pilot. Open an earlier result from the column heading to see it as it was. Export either table as CSV.
7. **Readiness, start to finish** (optional, about 5 minutes). Readiness, "Start a readiness assessment"; answer as Dana, sign in as Priya and answer, then back as Dana: start agreeing, set the agreed answers, finalise. The result page has the compass, priorities and strengths.
8. **Score an idea.** Ideas, "Repair and resale counter", Review. The AI's proposal is waiting: change a few scores, add a note, confirm. The result page shows the IQ, Value for Money, the compass, strengths and priorities. The scores cannot change afterwards; "Score again" makes a new assessment and keeps this one.
9. **Compare ideas.** In the ideas list tick two scored ideas and compare them side by side.
10. **Dimension importance.** Organisation, "Set dimension importance". It only decides the order of priorities whose scores tie; it never changes a score or the IQ.
11. **Activity log.** Organisation, "Open the activity log": who did what and when, with the method version and the AI model. Filter by action or person, export as CSV. Nothing in it can be edited.
12. **Other roles.** Sign in as Ines (investor) to show a read-only member, and as Amy (consultant) to show that she sees final results and confirmed ideas only, and neither the team nor the activity log.

## Not built yet

- AI advice on results and dimensions (Phase 6), PDF reports (Phase 7), going live (Phase 8).
- The AI's questions about the company before scoring (waits for Amy's answer on sending company details to the AI provider, and the AI key).
