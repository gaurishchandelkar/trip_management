# Spec: Personalised greeting

## Expected outcome

A user can type a name and be greeted by it ("Hello, Ada!"). Without a name, the greeting stays "Hello, World!".

## Constraints

- `GET /api/hello` without parameters keeps returning `{"message": "Hello, World!"}`.
- `/api/health` is unchanged.
- No new dependencies, no persistence.
- The layer order stays `api` → `services` → `domain`, and validation lives at the API boundary.

## Acceptance criteria

- [x] Given no `name`, when `GET /api/hello` is called, then it returns `200 {"message": "Hello, World!"}`
- [x] Given `name=Ada`, when `GET /api/hello` is called, then it returns `200 {"message": "Hello, Ada!"}`
- [x] Given a name with Unicode letters, spaces, hyphens or apostrophes (`Zoë`, `Mary Jane`, `Jean-Luc`, `O'Brien`), then it is greeted as given
- [x] Given a name longer than 50 characters, then the API returns `422 {"detail": "Invalid request"}`
- [x] Given a name containing other characters (`<script>`, digits, `%`), or leading/trailing spaces, or an empty value, then the API returns `422 {"detail": "Invalid request"}`
- [x] Given the page, when the user enters a name and presses **Greet**, then the heading shows "Hello, <name>!"
- [x] Given the page, when the user submits an invalid name, then a validation message is shown, and nothing from the input is rendered as HTML

## Non-functional requirements

- **Security:** strict allow-list validation on the server. The input box's `maxLength` on the client is a convenience, not the control. Error responses never echo the input.
- **Accessibility:** the input has a visible label, and errors are announced with `role="alert"`.
- **Performance:** no change. A single request per greeting.

## Failure conditions

- Invalid name → `422` with the generic body above, and the UI shows "Please enter a valid name (letters, spaces, hyphens and apostrophes, up to 50 characters)."
- Backend unavailable → the existing "Could not load greeting" alert.

## Definition of Done

- [x] All acceptance criteria are covered by passing tests (unit, integration, E2E)
- [x] `npm run check` passes
- [x] `docs/SPEC.md` and `docs/STATUS.md` are updated

## Out of scope

Remembering names, internationalised greetings, rate limiting.
