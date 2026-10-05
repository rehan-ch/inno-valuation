---
name: review-pr
description: Full pre-merge review of the current branch. Runs the code review and the methodology check in parallel, then the test suites, and merges everything into one verdict.
disable-model-invocation: true
allowed-tools: Bash(git diff *) Bash(git log *) Bash(git status *)
---

## Branch summary

!`git log --oneline main..HEAD 2>/dev/null || git log --oneline -10`

## Changed files

!`git diff --name-only main...HEAD 2>/dev/null || git diff --name-only HEAD`

## Task

1. Run code-reviewer and methodology-guardian in parallel on this branch.
2. Run test-runner on `bin/test-scoring`, then on the full suites.
3. Merge the three reports into one verdict:
   - Critical and BLOCK items (must fix)
   - Should fix
   - Test results
   - Ready to merge: yes or no, with the single most important reason.
