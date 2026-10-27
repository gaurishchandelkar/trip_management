---
name: plan
description: Write a phased implementation plan for a spec in docs/plans/, then stop for human approval. Use after /spec and before any implementation.
argument-hint: <spec name>
---

# /plan: Stage 2, Plan

Plan the spec `docs/specs/$ARGUMENTS.md`. If it doesn't exist, stop and suggest `/spec`.

## Steps

1. Read the spec, `docs/RULES.md`, `docs/CODING_GUIDELINES.md`, `docs/PROCESS.md`, and the code it touches.
2. Copy `docs/templates/PLAN_TEMPLATE.md` to `docs/plans/PLAN_$ARGUMENTS.md` and set `Status: **Awaiting approval**`.
3. Write the approach: which layers change, the design, and the main trade-off.
4. Split the work into 2–6 phases, each building on the last and each ending in a state where the checks pass.
5. Give every phase checkbox success criteria that can be verified: a named test, command output, an API response, or a browser check through the Playwright MCP server.
6. Fill in **Human attention needed**: the decisions, risks, new dependencies, and any changes to security or harness files.
   - Before naming a new dependency or its version, check what's current and what it requires: `npm view <pkg> version engines peerDependencies`, or `uv pip index versions <pkg>`. Don't name versions from memory.
7. Add a `### Spec coverage` table under **Final verification** with one row per acceptance criterion. Name each test as `` `path::test name` ``: a Python `def` name, or a vitest title exactly as quoted, `%s` placeholders and all. Name tests that don't exist yet as you plan to write them. `scripts/harness-config.test.mjs` fails on a row that names no test, and, once the plan's status is **Done**, on any name that matches no test.
8. Check the plan:
   - Every acceptance criterion in the spec maps to at least one success criterion.
   - No phase depends on code from a later phase.
   - Nothing in the plan goes beyond the spec.
   - When the change replaces or automates a manual step, search `.claude/skills/`, `docs/` and `scripts/` for that step, and list each place that changes.

## Stop

**Write no code, create no branches, and don't commit.** Summarize the plan and the human-attention items.
Ask the human to review it. On approval, the human sets `Status: **Approved**` or says so, then runs `/implement $ARGUMENTS`.
