# Plan: Personalised greeting

Spec: `docs/specs/personalised-greeting.md`
Status: **Done** <!-- Awaiting approval | Approved | In progress | Done -->
Approved: 2026-10-25 by the repo owner, as the Iteration 6 reference example in `docs/PLAN.md`.

## Approach

The domain gets a `greeting_for(name)` rule with the "World" default. The service passes an optional name through.
The API declares `name` as an optional query parameter with `max_length=50` and an allow-list pattern, and one validation handler maps every request validation error to a generic `422 {"detail": "Invalid request"}`, so input is never echoed back.
The frontend adds a labelled form. `api.ts` sends the name in the query string and raises a typed `InvalidNameError` on 422, which the UI shows as a validation message.
The trade-off: the generic 422 body hides which rule failed. That's simpler and safer, at the cost of less precise errors, and the UI's message lists the rules anyway.

## Human attention needed

- **Decision:** the allowed characters are Unicode letters, single spaces, hyphens and apostrophes between letters, from 1 to 50 characters. This rejects names with digits or periods ("J.R.").
- **Decision:** the validation error body is generic for *all* request validation errors, not only `name`.
- No new dependencies, and no changes to harness files.

## Phase 1: Domain and service

- `greeting_for(name: str | None) -> Greeting` in `backend/domain/greeting.py`
- `get_greeting(name: str | None = None)` in the service

Success criteria:
- [x] Unit tests: no name → "Hello, World!"; "Ada" → "Hello, Ada!"
- [x] `npm run check -- lint unit architecture` passes

## Phase 2: API validation

- An optional `name` query parameter with `max_length=50` and the allow-list pattern
- A `RequestValidationError` handler returning `422 {"detail": "Invalid request"}`

Success criteria:
- [x] Integration tests: default, `Ada`, `Zoë`, `Mary Jane`, `Jean-Luc`, `O'Brien` → 200 with the expected message
- [x] Integration tests: 51 characters, `<script>`, `R2D2`, `100%`, `" Ada"`, empty → 422 `{"detail": "Invalid request"}` without echoing the input
- [x] `npm run check -- lint unit integration architecture` passes

## Phase 3: Frontend form

- `fetchGreeting(name?)` sends `?name=` only when a name is given, and throws `InvalidNameError` on 422
- `App` shows the default greeting on load, plus a form ("Your name" label, `maxLength=50`, **Greet** button) that trims input and shows the greeting or the validation message

Success criteria:
- [x] Vitest: the query string is built correctly; 422 → `InvalidNameError`; the form greets; an invalid name shows the validation alert
- [x] Frontend coverage stays at or above 80%, and `npm run check -- build lint unit` passes

## Phase 4: End-to-end and docs

- Playwright: greet "Ada"; submit `<script>alert(1)</script>` → validation message, no dialog, no injected element
- Update `docs/SPEC.md` and `docs/STATUS.md`

Success criteria:
- [x] `npm run check -- functional` passes, with both new E2E tests
- [x] `docs/SPEC.md` documents the `name` parameter and the 422 behavior

## Final verification

- [x] `npm run check` passes
- [x] Every acceptance criterion in the spec is covered by a test
