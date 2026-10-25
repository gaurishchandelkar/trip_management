---
name: implement
description: Implement an approved plan phase by phase with tests, verification and one commit per phase. Use only after a human has approved the plan.
argument-hint: <plan name>
---

# /implement: Stages 3–4, Implement and Verify

Implement `docs/plans/PLAN_$ARGUMENTS.md`.

## Gate

- If the plan's status isn't **Approved**, and the human hasn't approved it in this conversation, stop and ask.
- If the human approved it in conversation, set `Status: **Approved**` in the plan and record the approval date.

## Steps

1. If you're on `main`, create the branch `feat/$ARGUMENTS`.
2. Set the plan status to **In progress**.
3. For each phase, in order and without stopping between phases:
   1. Build it, with tests: unit tests for logic, integration tests for API behavior, and E2E for user-visible flows.
   2. Run the fast stages: `npm run check -- lint unit integration`.
   3. Check every success criterion. For UI criteria, use the Playwright MCP browser.
   4. Tick the criteria in the plan and update `docs/STATUS.md`.
   5. Commit with the message `<plan name>: phase N - <summary>`. If the pre-commit hook fails, fix the cause and commit again.
4. After the last phase, run the full `npm run check`, update `docs/SPEC.md` for any new behavior, and set the plan status to **Done**.

## Rules

- Build only what the plan says. If the plan turns out to be wrong, stop and propose a change to it.
- Never weaken a check to make it pass: no suppressions, no lowered thresholds, no skipped tests.
- If the same check fails three times, stop and ask.

## Report

Give a table of the success criteria, each with its evidence (test name or command output), the final `npm run check` result, and any deviations. Suggest `/ship $ARGUMENTS`.
