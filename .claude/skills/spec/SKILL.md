---
name: spec
description: Turn a feature request into an agent-ready spec in docs/specs/. Use at the start of any new feature or significant change, before planning.
argument-hint: <feature request>
---

# /spec: Stage 1, Specify

Turn this request into an agent-ready spec: **$ARGUMENTS**

## Steps

1. Read `docs/templates/SPEC_TEMPLATE.md`, `docs/SPEC.md`, `docs/SECURITY_GUIDELINES.md`, and the code the request touches.
2. Pick a short kebab-case name and copy the template to `docs/specs/<name>.md`.
3. Fill in every section from the request and the code:
   - **Acceptance criteria** must be testable *Given / when / then* statements. Each one becomes a test.
   - **Failure conditions** must cover invalid input, dependency failure, and limits such as size, rate and time.
   - **Constraints** must name the existing behavior that has to stay the same.
4. Don't guess. Collect a question for each section you can't fill in confidently.
5. Ask the human all of the open questions in one message, then update the spec with the answers.

## Stop

Write no code and make no plan. Report the spec path and the decisions you need confirmed, then suggest `/plan <name>`.
