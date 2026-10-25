# Spec: <feature name>

> Copy this file to `docs/specs/<name>.md`. Every section is required.
> An agent drafting a spec asks the human about any section it can't fill in from the request.

## Expected outcome

What changes for the user or the system, in one or two sentences.

## Constraints

What must not change and which limits apply: existing behavior, performance budgets, stack, compatibility.

## Acceptance criteria

Specific statements that can be tested. Each one becomes at least one test.

- [ ] Given ..., when ..., then ...

## Non-functional requirements

Performance, security, accessibility, observability, cost.

## Failure conditions

How the feature must behave when things go wrong: invalid input, dependency down, timeouts.

## Definition of Done

- [ ] All acceptance criteria are covered by passing tests
- [ ] `npm run check` passes
- [ ] `docs/SPEC.md` and `docs/STATUS.md` are updated
- [ ] <feature-specific items>

## Out of scope

What this spec deliberately does not cover.

---

## Worked example: weak vs agent-ready

**Weak:** "Add caching to the API."

**Agent-ready:**

- **Expected outcome:** Product metadata responses are served from an in-memory cache, cutting repeat lookups.
- **Constraints:** Authorization behavior is unchanged. A user must never see a cached product they aren't allowed to see. No new infrastructure.
- **Acceptance criteria:**
  - [ ] A second request within 5 minutes is served from the cache (cache hit)
  - [ ] A request after 5 minutes refetches (expiry)
  - [ ] Updating a product invalidates its cache entry immediately (invalidation)
  - [ ] An unauthorized request for a cached product still returns 403
- **Non-functional:** Cache memory is bounded (LRU, at most 10k entries), and the hit ratio is logged.
- **Failure conditions:** If the cache fails, the request falls through to the source; it never returns stale data after an update.
- **Definition of Done:** The four acceptance tests pass, `npm run check` is green, and the TTL is documented in `SPEC.md`.
