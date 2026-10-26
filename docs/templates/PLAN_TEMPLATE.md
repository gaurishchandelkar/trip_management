# Plan: <feature name>

Spec: `docs/specs/<name>.md`
Status: **Awaiting approval** <!-- Awaiting approval | Approved | In progress | Done -->

## Approach

Two to five sentences: the design, which layers it touches, and the main trade-off.

## Human attention needed

Decisions, risks or assumptions a reviewer should look at. Write "None" if there are none.

## Phase 1: <name>

- What gets built

Success criteria:
- [ ] <test, command output, API response or browser check>
- [ ] <for a new check or safeguard: a negative proof. Temporarily break the code, or run the check against the old version, and show the check fails while nearby checks still pass. Then revert>

## Phase 2: <name>

- What gets built

Success criteria:
- [ ] ...

## Final verification

- [ ] `npm run check` passes
- [ ] Every acceptance criterion in the spec is covered by a test (table below)

### Spec coverage

Name each test as `path::test name`: a Python `def`, or a vitest title exactly as quoted. `scripts/harness-config.test.mjs` fails on a row that names no test, and, once Status is **Done**, on a name that matches no test.

| Spec acceptance criterion | Tests |
|---|---|
| <criterion> | `e2e/test_journeys.py::test_<journey>`, `frontend/src/<File>.test.tsx::<title>` |
