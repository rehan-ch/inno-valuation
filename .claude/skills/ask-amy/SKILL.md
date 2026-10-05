---
name: ask-amy
description: Draft the current list of open methodology questions as a short message for Amy, in simple wording.
disable-model-invocation: true
---

## Open questions right now

!`grep -n -B1 "Status: OPEN" docs/methodology/open-questions.md || true`

## Task

Delegate to spec-keeper: draft one message to Amy covering only the OPEN questions listed above. Group them by topic, number them, one sentence each, options as a short list. Plain English, no technical words, no em dashes. End with one line asking her to reply with each number and her choice. Then show me the draft.
