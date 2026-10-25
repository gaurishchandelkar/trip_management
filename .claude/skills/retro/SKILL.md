---
name: retro
description: Run the harness flywheel - turn failures, review feedback and successful patterns from recent work into concrete harness improvements logged in docs/HARNESS_LOG.md. Use after every PR, an escaped defect, or repeated review feedback.
argument-hint: <plan name, PR, or incident description>
---

# /retro: Stage 6, Learn

Retrospective for: **$ARGUMENTS**

## Gather signals

Look through the plan, the commits (`git log main..HEAD` or the merged range), reviewer findings, failed checks, and anything the human reports. Find:

- Checks that failed and then needed fix-up commits
- Defects found after "done" (escaped defects)
- Reviewer findings, especially ones that came up before
- Steps that were manual or repeated
- Approaches that worked well and should be reused

## Classify each signal

| Feedback signal | Harness improvement |
|---|---|
| Escaped defect | New test |
| Architecture violation | New rule (and an import-linter or ESLint contract) |
| Security issue | New safeguard (lint rule, guard hook rule, scan) |
| Repeated review feedback | Updated `docs/CODING_GUIDELINES.md` |
| Repetitive engineering task | New skill in `.claude/skills/` |
| Successful pattern | Reusable skill or template |
| Harness defect (a check, hook or metric gave false or misleading evidence) | Fix it, with a test proving the fix |

Choose the strongest improvement you can: **enforced beats documented**. A lint rule beats a guideline, and a test beats a note.

## Act

1. Add one entry per signal to `docs/HARNESS_LOG.md`, in the format at the top of that file.
2. Implement the improvements that don't touch protected harness files, each with a test proving the safeguard catches the original problem.
3. For changes to protected files (`.claude/`, `.github/`, `lefthook.yml`, rule docs), draft the change and ask the human to approve it.
4. Run `npm run check` and commit with the message `retro: <summary>`.

## Report

List the signals found, the improvement chosen for each, and which ones still need human approval.
