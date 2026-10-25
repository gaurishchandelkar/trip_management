# Plan: Members and groups

Spec: `docs/specs/members-and-groups.md`
Status: **In progress** <!-- Awaiting approval | Approved | In progress | Done -->
Approved: 2026-10-25 by the repo owner, in conversation.

## Approach

The backend gets a new `storage` layer between `services` and `domain`: SQLAlchemy 2.x Core tables on a local SQLite file, behind a `Store` whose `transaction()` hands out typed repository methods that take and return domain dataclasses. Services hold the use cases and every rule (uniqueness, ownership, limits, session expiry) and raise domain errors. The API maps those errors to the fixed status and message pairs in the spec, so no layer above `storage` imports SQLAlchemy and no layer below `api` imports FastAPI.
A session is a random token in an `HttpOnly`, `SameSite=Strict` cookie, stored server-side as a SHA-256 hash; a FastAPI dependency turns the cookie into the acting member for every protected route.
The frontend replaces the greeting with a single-page app (no router dependency) whose top-level state is a discriminated union: checking session → signed out (register and sign-in forms) → signed in (my groups, create, request by name, browse, group detail).
The main trade-off: **SQLAlchemy 2.x over SQLModel**. SQLModel would let one class serve as both table and API model, but it couples the API schema to the database, lags SQLAlchemy releases, and types less cleanly under pyright strict. SQLAlchemy keeps the Pydantic API models, the tables and the domain dataclasses separate, at the cost of mapping code in `storage`.

### API

All bodies are JSON with `extra="forbid"`. Every route except the first three needs a session cookie.

| Method | Path | Success | Purpose |
|---|---|---|---|
| GET | `/api/health` | `200 {"status": "ok"}` | Unchanged |
| POST | `/api/members` | `201 {user_id, display_name}` | Register |
| POST | `/api/sign-in` | `200 {user_id, display_name}` + `Set-Cookie` | Start a session |
| POST | `/api/sign-out` | `204`, cookie cleared | End the session |
| GET | `/api/me` | `200 {user_id, display_name}` | Who am I (used on page load) |
| GET | `/api/me/groups` | `200 [group summary]` | Groups I own or belong to |
| POST | `/api/groups` | `201 group summary` | Create a group |
| GET | `/api/groups?q=` | `200 [group summary]`, at most 50, by name | Browse and search |
| GET | `/api/groups/{group_id}` | `200 group detail` | Detail: members for members, plus pending requests for the owner |
| POST | `/api/groups/{group_id}/join-requests` | `201 {request_id, group_id, status}` | Ask to join from the browse list |
| POST | `/api/join-requests` `{group_name}` | `201 {request_id, group_id, status}` | Ask to join by exact name |
| POST | `/api/join-requests/{request_id}/approve` | `200 {request_id, group_id, status}` | Owner approves |
| POST | `/api/join-requests/{request_id}/reject` | `200 {request_id, group_id, status}` | Owner rejects |

A group summary is `{group_id, name, description, owner_display_name, member_count, my_status}`, where `my_status` is `owner`, `member`, `pending` or `none`.

### Data

`members(user_id PK, display_name)`, `sessions(token_hash PK, user_id FK, expires_at)`, `groups(group_id PK, name, name_key UNIQUE, description, owner_id FK)`, `memberships(group_id, user_id) PK`, `join_requests(request_id PK, group_id, user_id, status)` with a partial unique index on `(group_id, user_id) WHERE status = 'pending'`. `name_key` is the casefolded name, so uniqueness ignores case for any script. Requests are never deleted; approve and reject are a conditional `UPDATE … WHERE status = 'pending'`, so a second decision changes no rows and returns `404`.

## Human attention needed

- **New dependency:** `sqlalchemy` 2.x (runtime). Approved in the spec (D3); this plan picks SQLAlchemy over SQLModel for the reasons above. `uv.lock` changes and pip-audit must stay clean.
- **Config change, import-linter (`pyproject.toml`):** the layers contract becomes `main → api → services → storage → domain`, and a new forbidden contract stops `api`, `services` and `domain` from importing `sqlalchemy`. This tightens the rules; it relaxes none.
- **Spec interpretation, user ID case:** the spec says registering `ADA` after `ada` returns `409`, but its pattern allows only lower-case. I'll accept upper-case letters in the input and lower-case them before storing and comparing (for sign-in too), so `ADA` → `409`, not `422`. The stored and displayed ID is always lower-case.
- **Gap in the spec, session lifetime:** the spec mentions expired sessions but sets no lifetime. I propose **7 days from sign-in**, fixed, not sliding. Expired sessions are rejected and deleted when presented.
- **Cookie without `Secure`:** the app runs over plain HTTP on `127.0.0.1` (local, trusted use only per the spec), and `TestClient` wouldn't send a `Secure` cookie. Adding `Secure` belongs with real authentication and deployment.
- **403 vs 404 on approve/reject:** the spec requires `403` for a non-owner, which lets a non-owner tell that a pending request ID exists. Lookups happen first (`404` if missing or decided), then the owner check (`403`). Request IDs reveal nothing else.
- **Browse is capped at 50 with no paging:** beyond 50 groups, members narrow the list with search. Paging isn't in the spec.
- **Coverage comes from unit tests only** (`[tool.coverage.run]` measures `pytest backend/tests/unit`). Service and storage unit tests therefore run against a real SQLite file in `tmp_path`, never a mock and never shared between tests. API dependencies and error mapping get unit tests too, while full HTTP flows stay in `backend/tests/integration`.
- **Performance test:** one integration test seeds 1,000 members and 1,000 groups and asserts browse, search and group detail each answer in under 200 ms. It could be noisy on a slow CI runner. If it flakes, I'll stop and ask rather than loosen it.
- **E2E harness change (`e2e/conftest.py`):** the backend under test gets `TRIP_DB_PATH` pointing at the session's temp dir, so E2E never touches dev data. Its existing S603 exemption is unaffected (the argv doesn't change). Multi-user journeys open a second browser context for the other member.
- **Removed:** `/api/hello`, the greeting domain/service, the greeting UI and all their tests (D4). `docs/CODING_GUIDELINES.md` mentions "the loaded greeting" as the initial state to wait for; I'll update that line to "the loaded session check".
- No changes to `.claude/`, `.github/`, `lefthook.yml` or CI config.

## Phase 1: Storage foundation

- `uv add sqlalchemy` (2.x)
- `backend/domain/`: `Member`, `Group`, `GroupSummary`, `JoinRequest`, `MembershipStatus` dataclasses, the validation-free rules (`casefold` name key, limits as constants: 50 members, 20 owned groups, 20 pending requests), and errors `Conflict(reason)`, `NotFound`, `Forbidden`, `LimitReached`, `Unauthenticated`, `StorageUnavailable`
- `backend/storage/`: SQLite engine (foreign keys on, `NullPool` so no connection holds the file between requests, 5 s busy timeout), the five tables and indexes, `create_schema()`, and `Store.transaction()` that commits on success, rolls back on any exception, and turns SQLAlchemy `DBAPIError` into `StorageUnavailable`
- `backend/main.py`: `create_app(db_path: Path | None = None)` reads `TRIP_DB_PATH` with a default of `trip.db` in the repo root, creates the schema on startup, and keeps the `Store` on `app.state`
- `.gitignore`: `/trip.db*`
- import-linter: the new layer and the `sqlalchemy` forbidden contract

Success criteria:
- [x] Unit tests (`backend/tests/unit/test_storage.py`): the schema is created on a fresh file; a transaction that raises leaves no rows behind; a duplicate `name_key` and a second pending request for the same member and group are refused by the database; a conditional decision on an already-decided request changes no rows
- [x] Unit test: a corrupted database file (garbage bytes) makes `Store.transaction()` raise `StorageUnavailable`
- [x] Unit test: `create_app(db_path=tmp)` creates the file there; with no argument and no `TRIP_DB_PATH`, the path is `<repo>/trip.db` (asserted on the resolved path, without creating it)
- [x] Negative proof: temporarily `import sqlalchemy` in `backend/services/` → `npm run check -- architecture` fails on the new contract while the layers contract passes; revert
- [x] `npm run check -- lint unit architecture security` passes

## Phase 2: Members and sessions API

- Services: `register(user_id, display_name)`, `sign_in(user_id)` returning a fresh token (`secrets.token_urlsafe(32)`, stored hashed, expires in 7 days), `sign_out(token)`, `current_member(token)` (missing, unknown or expired → `Unauthenticated`), with an injectable clock; INFO log on sign-in with the user ID only
- API: Pydantic request models (`user_id` 3–30 chars, `^[A-Za-z][A-Za-z0-9_-]*$`, lower-cased; `display_name` reuses the existing name pattern; `password` 1–128 chars, accepted and discarded); routes `POST /api/members`, `POST /api/sign-in`, `POST /api/sign-out`, `GET /api/me`; a `current_member` dependency reading the `session` cookie (`HttpOnly`, `SameSite=Strict`, `Path=/api`, `Max-Age` 7 days); exception handlers mapping domain errors to `401/403/404/409/503` with the spec's fixed bodies
- A pure ASGI middleware that counts request body bytes and returns `413 {"detail": "Request too large"}` past 4 KB, with or without `Content-Length`
- The greeting backend stays for now, so the current frontend and E2E still pass

Success criteria:
- [x] Integration tests (`backend/tests/integration/test_members.py`): register `ada`/`Ada Lovelace` → `201 {"user_id": "ada", "display_name": "Ada Lovelace"}`; register `ada` again and `ADA` → `409 {"detail": "User ID already taken"}`
- [x] Integration tests: user IDs `ab`, 31 chars, `1ada`, `ada!`, `<script>`; display names `R2D2`, 51 chars, empty; a missing field, an unknown field and a wrong type → `422 {"detail": "Invalid request"}`, and the response body never contains the input
- [x] Integration tests: sign in as `ada` with password `anything` → `200`, a `session` cookie with `HttpOnly` and `SameSite=Strict`, then `GET /api/me` → `200` with Ada's display name; sign in as `bob` → `401 {"detail": "Invalid user ID or password"}` with no `Set-Cookie`; empty, missing or 129-char password → `422`
- [x] Integration tests: after `POST /api/sign-out`, the old cookie on `GET /api/me` → `401`; with no cookie, `GET /api/me` → `401`; with a session whose clock has passed 7 days → `401`
- [x] Integration test: the stored session row holds a hash, not the cookie value, and no table has a password column
- [x] Integration tests: a 5 KB body to `POST /api/members` → `413`, with and without `Content-Length`; a corrupted database file after startup → `503 {"detail": "Service unavailable"}`
- [x] Unit tests: each domain error maps to its status and body; the sign-in log record contains the user ID and not the display name or password (`caplog`)
- [x] `npm run check -- lint unit integration architecture` passes

## Phase 3: Groups and joining API

- Services: `create_group`, `my_groups`, `browse_groups(q)`, `group_detail(group_id)`, `request_to_join(group_id)`, `request_to_join_by_name(name)`, `approve(request_id)`, `reject(request_id)`. The acting member always comes from the session. Rules: name uniqueness by `name_key`; already member or owner → `Conflict("Already a member")`; duplicate pending → `Conflict("Request already pending")`; limits → `LimitReached`; approve/reject look up the pending request (`NotFound`), then check ownership (`Forbidden`), then do the conditional update; approve also checks the 50-member limit. INFO logs for group creation and decisions, user IDs and group IDs only
- API: `group name` 1–60 chars of letters, digits, spaces and `-'&.,`, starting with a letter or digit, no leading, trailing or double spaces; `description` 0–200 chars, no control characters; `q` 1–60 chars of the same set; the routes in the table above
- Group detail returns `members` only when the actor is a member or owner, and `pending_requests` (request ID, requester display name) only for the owner

Success criteria:
- [x] Integration tests (`backend/tests/integration/test_groups.py`): create `Goa 2027` → `201` with `my_status: "owner"` and `member_count: 1`; create `goa 2027` → `409 {"detail": "Group name already taken"}`; names `""`, 61 chars, `" Goa"`, `"Goa  2027"`, `Goa_2027`, `<b>`; a 201-char description → `422`
- [x] Integration tests: browse lists name, owner display name, member count and the caller's status for owner, member, pending and none; `?q=goa` returns only names containing "goa" in any case; 60 groups → 50 returned, sorted by name
- [x] Integration tests: request by ID → `201 pending`, and browse then shows `pending`; again → `409 {"detail": "Request already pending"}`; owner or member requesting → `409 {"detail": "Already a member"}`; request by name `goa 2027` → `201` for `Goa 2027`; unknown name or group ID → `404 {"detail": "Not found"}`
- [x] Integration tests: owner's detail lists pending requests with display names; approve → the requester appears in members, `my_status: "member"`, request no longer pending; reject → not a member, may request again (`201`); a member's detail shows members but no pending requests; a non-member's detail shows neither
- [x] Integration tests: a non-owner approving or rejecting → `403 {"detail": "Forbidden"}` and nothing changes; an unknown or already-decided request → `404`; two approvals of the same request from two threads → one `200`, one `404`, exactly one membership
- [x] Integration tests: the 21st owned group, 21st pending request, and approving into a 50-member group → `409 {"detail": "Limit reached"}`
- [x] Integration tests: every Phase 3 route without a cookie → `401`
- [x] Integration test: with 1,000 members and 1,000 groups seeded, browse, search and group detail each answer in under 200 ms
- [x] Unit tests cover the service rules above against a `tmp_path` database, and backend unit coverage stays at or above 80%
- [x] `npm run check -- lint unit integration architecture` passes

## Phase 4: Sign-in UI, retire the greeting

- Remove `/api/hello`, `backend/domain/greeting.py`, `backend/services/greeting.py`, the greeting UI and every greeting test (unit, integration, E2E outside and inside)
- `frontend/src/api.ts`: `register`, `signIn`, `signOut`, `getMe`, typed errors (`InvalidInputError` on 422, `ConflictError` on 409, `SignedOutError` on 401, `NotFoundError` on 404, `UnavailableError` on 503 and other failures)
- `App`: on load calls `GET /api/me`; shows "Loading…", then either the signed-out view (**Register** form: User ID, Display name; **Sign in** form: User ID, Password as `type="password"`, with the note "Passwords aren't checked yet.") or a signed-in header with the display name and a **Sign out** button. Field-specific hints on 422, "That user ID is already taken." on 409, "Something went wrong, please try again" on 503 and network failures. Any `SignedOutError` returns to the signed-out view
- `e2e/conftest.py` passes `TRIP_DB_PATH` in the temp dir; E2E tests use a unique user ID per test
- `docs/CODING_GUIDELINES.md`: the initial state to wait for becomes the loaded session check

Success criteria:
- [x] Vitest: each `api.ts` function sends the right method, path and JSON body and maps each status to its error; `App` shows the signed-out forms with labels, registers then signs in, shows the display name, signs out, returns to sign-in on a `SignedOutError`, and shows the 503 message
- [x] Vitest: a display name of `<img src=x onerror=alert(1)>` returned by the API renders as literal text and creates no `img` element
- [x] E2E outside (`test_journeys.py`): register, sign in and see the display name; sign out and see the sign-in form; sign in as an unregistered ID and see the error; the password field has `type="password"` and the "aren't checked yet" note is visible
- [x] E2E inside (`test_network_contract.py`): page load makes exactly `GET /api/me` (401); register makes exactly `POST /api/members` (201); sign-in makes exactly `POST /api/sign-in` (200) and the password never appears in any later request; sign-out makes exactly `POST /api/sign-out` (204)
- [x] `create_app().openapi()` no longer contains `/api/hello`; `rg -i "hello|greeting" backend frontend/src e2e` finds nothing
- [x] Browser check with the Playwright MCP server against `npm run dev`: register, sign in, reload (still signed in), sign out
- [x] `npm run check` passes

## Phase 5: Groups UI and docs

- `api.ts`: `getMyGroups`, `createGroup`, `browseGroups(q)`, `getGroup`, `requestToJoin(groupId)`, `requestToJoinByName(name)`, `approve`, `reject`
- Signed-in view: **My groups** list; **Create group** form (Name, Description); **Request to join** form (Group name); **Browse groups** with a search box and a **Request to join** button per group (hidden when `my_status` isn't `none`, "Request pending" shown when it's `pending`); a group detail view with description, owner, member list for members, and pending requests with **Approve** and **Reject** buttons for the owner. Messages: "No group has that name.", "Request already pending.", "You're already a member.", "That group name is already taken.", "Limit reached."
- Docs: `docs/SPEC.md` (product, API table, local-and-trusted-use-only warning, limits, session lifetime), `docs/STATUS.md`, `docs/TECH_STACK.md` (SQLite + SQLAlchemy 2.x, `TRIP_DB_PATH`)

Success criteria:
- [ ] Vitest: each new `api.ts` function's request and error mapping; create group shows it in My groups; browse search sends `?q=`; the request button becomes "Request pending"; the request-by-name 404 shows "No group has that name."; the owner sees Approve and Reject and they call the right endpoints; a group name and description containing markup render as text
- [ ] Frontend coverage stays at or above 80%
- [ ] E2E outside, two browser contexts: Ada creates `Goa <unique>`; Bob finds it by browsing and requests; Ada sees Bob's pending request and approves; Bob's group list now shows it and he sees the member list. A second journey: Carol requests by typing the name in lower case; Ada rejects; Carol sees the request button again
- [ ] E2E inside: create group makes exactly `POST /api/groups` (201) and then `GET /api/me/groups`; browse search makes exactly `GET /api/groups?q=<term>`; request from browse makes exactly `POST /api/groups/<id>/join-requests` (201); request by name makes exactly `POST /api/join-requests` with `{"group_name": …}`; approve makes exactly `POST /api/join-requests/<id>/approve` (200) followed by `GET /api/groups/<id>`
- [ ] Browser check with the Playwright MCP server against `npm run dev`: the two-member approve journey, keyboard only (Tab and Enter) for Bob's request
- [ ] `docs/SPEC.md`, `docs/STATUS.md` and `docs/TECH_STACK.md` updated
- [ ] `npm run check` passes

## Final verification

- [ ] `npm run check` passes
- [ ] Every acceptance criterion in the spec is covered by a test (mapping below)
- [ ] `code-reviewer` and `security-reviewer` run before `/ship`

### Acceptance criteria → success criteria

| Spec area | Covered in |
|---|---|
| Registration (201, 409 on case, 422) | Phase 2 integration; Phase 4 E2E |
| Sign in, password 422, unknown 401, sign out, no session 401 | Phase 2 integration; Phase 3 "no cookie" test; Phase 4 vitest and E2E |
| Create group, duplicate name, name/description 422 | Phase 3 integration; Phase 5 vitest and E2E |
| Browse with status, search | Phase 3 integration; Phase 5 vitest, E2E inside |
| Request by name, unknown name 404 | Phase 3 integration; Phase 5 vitest and E2E |
| Request, duplicate pending 409, already member 409 | Phase 3 integration; Phase 5 vitest |
| Owner sees pending; approve; reject and re-request | Phase 3 integration; Phase 5 E2E |
| Non-owner 403, unknown/decided 404, concurrent approve | Phase 3 integration |
| Member list for members only | Phase 3 integration; Phase 5 E2E |
| Frontend forms, labels, password field and note | Phase 4 vitest and E2E |
| Signed-in view: groups, create, request by name, browse | Phase 5 vitest and E2E |
| Text never rendered as HTML | Phase 4 and Phase 5 vitest |
| Limits, 413, 503, logging, performance | Phases 1–3 unit and integration |
