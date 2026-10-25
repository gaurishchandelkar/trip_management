# Spec: Members and groups

> Status: **ready for planning**. Decisions D1–D4 are recorded at the end. Trips themselves (itinerary, expenses) come in a later spec.

## Expected outcome

Friends can register as members, sign in with a user ID, and organise themselves into groups for trips.
Any member can create a group and becomes its owner. Other members find a group and ask to join it,
and they become members only once the owner approves.

## Constraints

- `/api/health` is unchanged.
- The Hello World greeting is retired (D4): `/api/hello`, the greeting UI and their unit, integration and E2E tests are removed, and the trip app becomes the home page.
- The layer order stays `api` → `services` → `domain`. Validation lives at the API boundary, and the domain stays free of FastAPI, Starlette and Uvicorn (import-linter contracts unchanged).
- Invalid input returns `422 {"detail": "Invalid request"}` and never echoes the input, as today.
- Storage is SQLite through SQLAlchemy 2.x or SQLModel (D3, dependency approved). No other new dependencies without approval. Persistence code lives in its own layer below `services`, so `domain` stays free of the ORM.
- No real credentials (D1): the password is required in the form but not checked, and it is never stored, logged or returned. No hashing, reset or third-party login in this spec.
- Nothing binds to `0.0.0.0`, and no secret or fixed password value is committed to the repo.
- Coverage gates stay at 80%. Every journey gets an outside E2E test and an inside network-contract test, like the existing ones.

## Acceptance criteria

### Registration

- [ ] Given no member with user ID `ada`, when someone registers with user ID `ada` and display name `Ada Lovelace`, then the member is created and `201` is returned with the user ID and display name
- [ ] Given a member `ada` exists, when someone registers `ada` or `ADA`, then `409 {"detail": "User ID already taken"}` is returned (user IDs are unique, case-insensitive, stored lower-case)
- [ ] Given a user ID that isn't 3–30 characters of lower-case letters, digits, `_` or `-` starting with a letter, or a display name that fails the existing name rule (1–50 letters, single spaces, hyphens or apostrophes), then `422 {"detail": "Invalid request"}` is returned

### Sign in and out

- [ ] Given a registered member `ada`, when they sign in with user ID `ada` and any non-empty password of up to 128 characters, then a session is started and the app shows their display name
- [ ] Given an empty or missing password, or one over 128 characters, when someone signs in, then `422 {"detail": "Invalid request"}` is returned
- [ ] Given no member `bob`, when someone signs in as `bob`, then `401 {"detail": "Invalid user ID or password"}` is returned and no session is started
- [ ] Given a signed-in member, when they sign out, then the session ends and any further request with it returns `401`
- [ ] Given no session, when any endpoint other than health, register and sign in is called, then `401` is returned

### Groups

- [ ] Given a signed-in member, when they create a group with a valid name (and optional description), then the group is created with them as owner and sole member
- [ ] Given a group named `Goa 2027` exists, when anyone creates `goa 2027`, then `409 {"detail": "Group name already taken"}` is returned (names are unique, case-insensitive)
- [ ] Given a group name that isn't 1–60 characters of letters, digits, spaces and `-'&.,`, or a description over 200 characters, then `422 {"detail": "Invalid request"}` is returned
- [ ] Given several groups, when a signed-in member browses groups, then they see each group's name, owner display name, member count and their own status for it (owner, member, pending or none)
- [ ] Given a search term, when a member browses groups, then only groups whose name contains the term (case-insensitive) are listed

### Joining

A member reaches a group in one of two ways (D2): by picking it from the browse list, or by typing its exact name (case-insensitive) in a **Request to join** form. Both create the same pending request.

- [ ] Given a group `Goa 2027`, when a member requests to join by typing `goa 2027`, then a pending request is created for that group
- [ ] Given no group with the typed name, when a member requests to join by name, then `404 {"detail": "Not found"}` is returned and the UI says no group has that name
- [ ] Given a member who isn't in group G and has no pending request for it, when they ask to join G, then a pending request is created and G shows "Request pending" for them
- [ ] Given a pending request, when the member asks again, then `409 {"detail": "Request already pending"}` is returned
- [ ] Given a member or owner of G, when they ask to join G, then `409 {"detail": "Already a member"}` is returned
- [ ] Given the owner of G, when they open G, then they see its pending requests with each requester's display name
- [ ] Given the owner approves a request, then the requester becomes a member of G and the request is no longer pending
- [ ] Given the owner rejects a request, then the requester doesn't become a member and may ask again later
- [ ] Given a member who isn't G's owner, when they approve or reject a request for G, then `403 {"detail": "Forbidden"}` is returned and nothing changes
- [ ] Given a request ID that doesn't exist or is no longer pending, when the owner approves or rejects it, then `404 {"detail": "Not found"}` is returned
- [ ] Given a member of G, when they open G, then they see its member list; a non-member sees only the browse details

### Frontend

- [ ] Given the app with no session, then it shows **Sign in** and **Register** forms with visible labels
- [ ] Given a signed-in member, then the app shows their groups, a **Create group** form, a **Request to join** form and a **Browse groups** view
- [ ] Given the sign-in form, then the password field is `type="password"` and the page states that passwords aren't checked yet
- [ ] Given any user-supplied text (display names, group names, descriptions), then it is rendered only as text, never as HTML

## Non-functional requirements

- **Security:**
  - Server-side allow-list validation on every field; client `maxLength` is a convenience only.
  - The session is an opaque random token from `secrets.token_urlsafe(32)`, sent as an `HttpOnly`, `SameSite=Strict` cookie, never a user ID the client can forge. State-changing requests are `POST` only.
  - Authorization is checked in the service layer: only the owner can approve or reject, and the acting member always comes from the session, never from the request body.
  - Error bodies are generic and never contain input, IDs of other users, SQL or stack traces.
  - Because there are no real passwords (D1), the app is for local and trusted use only. `docs/SPEC.md` says so.
- **Accessibility:** every input has a visible label, errors are announced with `role="alert"`, and every action is a real `<button>` reachable by keyboard.
- **Performance:** browse returns at most 50 groups per request; every endpoint answers in under 200 ms locally with 1,000 members and 1,000 groups.
- **Observability:** sign-in, group creation and approve/reject decisions are logged at INFO with user IDs only, no display names or free text.
- **Cost:** no new infrastructure.

## Failure conditions

- **Invalid input** (bad pattern, too long, missing field, unknown field, wrong type) → `422 {"detail": "Invalid request"}`; the UI shows a field-specific hint written by the frontend, never the server's echo.
- **Conflicts** (duplicate user ID, duplicate group name, duplicate request, already a member) → `409` with the messages above.
- **No or expired session** → `401`; the UI returns to the sign-in screen.
- **Not the owner** → `403 {"detail": "Forbidden"}`.
- **Unknown group or request** → `404 {"detail": "Not found"}`. A non-member can't tell a hidden resource from a missing one.
- **Concurrent approvals** (owner double-clicks, two tabs) → exactly one membership is created; the second call returns `404`.
- **Storage unavailable or corrupt** → `503 {"detail": "Service unavailable"}`; the UI shows "Something went wrong, please try again", and nothing is half-written (each change is one transaction).
- **Limits:** a group has at most 50 members, a member owns at most 20 groups and has at most 20 pending requests. Exceeding any → `409 {"detail": "Limit reached"}`.
- **Request body over 4 KB** → `413` or `422`, never processed.

## Definition of Done

- [ ] All acceptance criteria are covered by passing tests (unit, integration, E2E outside and inside)
- [ ] `npm run check` passes
- [ ] `docs/SPEC.md` and `docs/STATUS.md` are updated
- [ ] `docs/TECH_STACK.md` records SQLite + the chosen ORM, `uv.lock` is updated, pip-audit is clean, and `.gitignore` covers the local database file
- [ ] The database path comes from configuration with a safe local default; the schema is created on startup
- [ ] The E2E run uses its own throwaway database, so it never touches dev data
- [ ] `code-reviewer` and `security-reviewer` have run with no unresolved findings

## Out of scope

- Trips: itineraries, dates, expenses and splitting costs (next spec)
- Real authentication: password hashing, reset, email verification, OAuth, rate limiting on sign-in
- Inviting members by the owner, leaving a group, removing members, transferring or deleting a group
- Editing profiles or groups after creation
- Notifications (email, push, in-app badges)
- Deployment and multi-user hosting
- Database migrations (Alembic); the schema is created on startup until a later spec needs to change it

## Decisions

Confirmed by the human on 2026-10-25.

- **D1. Sign-in:** the form has a user ID and a password field. Any non-empty password is accepted for now; real passwords will be added ("fixed") in a later spec. The user must register first, so an unknown user ID is rejected.
- **D2. Joining:** a member picks a group from a searchable browse list, or requests one by typing its exact name. Both create a pending request that only the owner can approve or reject.
- **D3. Storage:** SQLite through an ORM. The new dependency is approved. `/plan` picks between SQLAlchemy 2.x and SQLModel and records why.
- **D4. Greeting:** retired. The trip app replaces the Hello World page and `/api/hello`; `/api/health` stays.
