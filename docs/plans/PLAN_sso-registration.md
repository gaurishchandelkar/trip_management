# Plan: Registration and sign-in with Google

Spec: `docs/specs/sso-registration.md`
Status: **In progress** <!-- Awaiting approval | Approved | In progress | Done -->
Approved: 2026-11-23 by the repo owner, in conversation, with joserfc + httpx2 for the OIDC adapter (D4 amended).

## Approach

The backend gets a new **identity** adapter, `backend/identity/`, beside `storage`. It speaks OpenID Connect to Google: discovery, the authorization URL, the code exchange with PKCE, and the ID-token check against Google's keys. It sits behind an `IdentityProvider` protocol that the services own, so services and integration tests use an in-process fake and never touch HTTP.
A new `services/auth.py` holds the use cases:
- start a sign-in, saving a single-use flow record;
- finish it, ending in one of four outcomes: signed in, needs registration, failed or cancelled;
- read and complete a pending registration;
- update the profile.
`storage` gains three tables (`identities`, `sign_in_flows`, `pending_registrations`) and a `mobile` column on `members`. Who may see a mobile number is decided in one service function.
The API adds the browser-facing routes:
- `GET /api/auth/google/start` and `GET /api/auth/google/callback`, which answer with redirects;
- the JSON routes `GET /api/auth/providers`, `GET` and `POST /api/auth/registration`, and `POST /api/me/profile`.
It also retires `POST /api/members` and `POST /api/sign-in`.
The frontend replaces the Sign in and Register forms with **Continue with Google**, and adds the **Finish registering** (`/register/complete`) and **Profile** (`/profile`) screens. It shows `@user-id` beside every name, and phone links for owners.
E2E runs against a small fake OpenID Connect server in `e2e/`, started on `127.0.0.1` by the fixture. So the real adapter, real cookies and real redirects are exercised end to end without contacting Google.

**Main trade-off, the OIDC library (changes D4, needs your approval):** I checked Authlib 1.9.10 under this repo's `pyright --strict`. Its OAuth client ships no type information, and a 10-line sample using `create_authorization_url` and `fetch_token` produced 4 `reportUnknown*` errors. Using it would need suppressions or a looser pyright mode for that module, which the hard lines forbid without asking. **joserfc 1.8.0** passed with 0 errors. It's the typed JOSE library Authlib itself depends on, by the same author, and it ships `py.typed`. So the plan uses:
- **joserfc** to verify the ID token (signature via JWKS, `iss`, `aud`, `exp`, `iat`, `nonce`);
- **httpx2**, already locked as a test dependency and moved to runtime, for discovery, JWKS and the token call;
- about 40 hand-written lines for the authorization URL and PKCE (`secrets` + SHA-256 + base64url).

The cost is that we own those 40 lines, and their unit tests. The gain is full static typing with no exceptions to the rules. If you'd rather have Authlib, the alternative is a `# pyright: basic` file-level mode for `backend/identity/`, which needs your explicit approval as a rule exception.

### API

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/api/auth/providers` | `200 {"providers": ["google"]}` or `{"providers": []}` | No session needed. Tells the signed-out screen whether to show the button |
| GET | `/api/auth/google/start?return_to=` | `302` to Google, flow cookie set | `404` when not configured |
| GET | `/api/auth/google/callback?code=&state=` (or `error=`) | `302` to `return_to`, `/register/complete`, `/?sign_in=failed` or `/?sign_in=cancelled` | Always a same-origin `Location` |
| GET | `/api/auth/registration` | `200 {display_name, return_to}` | Pending-registration cookie; `display_name` is `""` when Google's name fails the rule |
| POST | `/api/auth/registration` `{user_id, display_name, mobile}` | `201 {user_id, display_name, mobile}` + session cookie | `409 Account already linked` is new |
| POST | `/api/me/profile` `{display_name, mobile}` | `200 {user_id, display_name, mobile}` | |
| GET | `/api/me` | `200 {user_id, display_name, mobile}` | Gains `mobile` |
| `group` | | gains `owner_user_id` | |
| group detail | | `members: [{user_id, display_name, mobile?}]`, `pending_requests: [{request_id, user_id, display_name, mobile?}]` | `mobile` is present only for the owner |
| POST | `/api/members`, `/api/sign-in` | removed | Answer like any unknown route |

### Data

- `members(user_id PK, display_name, mobile)`, where `mobile` is `String(16)`.
- `identities(provider, subject)`: primary key on the pair, `user_id` a foreign key, and unique `(user_id, provider)`.
- `sign_in_flows(flow_hash PK, state_hash, nonce, code_verifier, return_to, expires_at)`. The cookie holds the random flow ID; only its hash and the state's hash are stored. The nonce and verifier are stored as they are, because the callback needs them, and the row is deleted when used.
- `pending_registrations(token_hash PK, provider, subject, suggested_name, return_to, expires_at)`.

Using a flow or a pending registration is a conditional `DELETE … RETURNING`, so a replay or a double submit finds nothing.

## Human attention needed

- **D4 change (decision):** joserfc plus httpx2 instead of Authlib plus httpx, for the pyright reason above. The new runtime dependencies are `joserfc` 1.8.0 (requires Python 3.11 or later, and `cryptography` 45.0.1 or later, which becomes a new transitive dependency) and `httpx2` 2.16 (already in `uv.lock` as a dev dependency). I checked versions on PyPI on 2026-11-23. On approval I'll amend D4 in the spec.
- **New environment variable not named in the spec:** `TRIP_PUBLIC_URL`, the app's own origin, with a default of `http://localhost:5173`. Google needs an exact redirect URI, and building it from the request's `Host` header would let a forged header choose where the callback goes. The redirect URI is `TRIP_PUBLIC_URL` + `/api/auth/google/callback`. E2E sets it to the preview server's address. You'll add its name to `.env.example` alongside the two Google variables.
- **New endpoint not named in the spec:** `GET /api/auth/providers`. The signed-out screen needs to know whether Google is configured, and the start route only says so with a redirect. This adds one call to the signed-out page load (`GET /api/me` then `GET /api/auth/providers`), which the inside E2E tests pin.
- **Harness file changes:**
  - `e2e/conftest.py` starts a third process, the fake OIDC server (`e2e/fake_google.py` under uvicorn). It uses a fixed argv, so it's the same as the existing S603 exemption.
  - It also passes the Google variables to the backends under test. The client secret is generated per session with `secrets.token_urlsafe`, so nothing is committed and detect-secrets stays quiet.
  - The `traffic` fixture's foreign-origin check allows exactly the fake server's origin, `http://127.0.0.1:8102`, and still fails on any other.
- **Screenshot set grows from 20 to 24**, adding the profile screen. Places that name 20 and change:
  - `e2e/test_screenshots.py` (`SCREENS`)
  - `scripts/screenshot-summary.mjs` (`SCREENS`)
  - `scripts/screenshot-summary.test.mjs`
  - `scripts/open-pr.mjs` (comment) and `scripts/open-pr.test.mjs`
  - `docs/PROCESS.md`, `docs/STATUS.md`, `README.md`
  - `.claude/skills/ship/SKILL.md`, a `.claude/` change that needs your approval in the PR

  The partial-or-stale refusal stays the same. Historical entries in `docs/HARNESS_LOG.md`, and the done spec and plan for CI screenshots, are left as they were.
- **A temporarily nullable `mobile` (Phases 2–3):** Phase 2 adds the new routes while the old forms still exist, so every phase can end with a full green `npm run check`. The old `POST /api/members` can't supply a mobile number, so the column is nullable until Phase 3 retires the old routes and makes it `NOT NULL`. Because of the fresh start, there's no migration in between. Delete your local `trip.db` after pulling.
- **An old `trip.db` stops startup:** after creating the schema, the store checks that `members.mobile` exists. If it doesn't, startup fails with "This database is from an older version. Delete trip.db and start again." The new tables are always created; only the old `members` table can't change without migrations.
- **Flow cookie `SameSite=Lax`:** required for the callback, as the spec says. Its path is `/api/auth`, and it holds only a random ID.
- **Cookies without `Secure`:** unchanged from today. The app runs over plain HTTP on localhost, and Google allows `http://localhost` redirect URIs for development.
- **Fake provider realism:** the fake server signs real RS256 tokens with a key generated at startup, publishes JWKS and discovery, checks PKCE and the redirect URI, and supports cancel. It doesn't imitate Google's consent screen. The real-Google check stays manual (Definition of Done).
- **Unit coverage includes the adapter.** Coverage is measured on unit tests only, so `backend/identity/` is tested with `httpx2.MockTransport` and tokens signed by a test key. That covers discovery, JWKS caching and rotation, timeouts, bad JSON, and every claim failure.
- **Removed tests:** the E2E journeys and inside tests for the user-ID forms are replaced (listed in Phase 3). The `unique_user_id` helper stays, because Finish registering still takes a user ID.

## Phase 1: OIDC adapter and fake provider

- `uv add joserfc httpx2` (httpx2 moves from dev to runtime). `uv.lock` updated.
- `backend/services/identity_port.py`:
  - `IdentityProvider` protocol: `authorization_url(state, nonce, code_challenge) -> str` and `verified_identity(code, code_verifier, nonce) -> Identity`;
  - `ProviderUnavailable` and `IdentityRejected` errors;
  - `Identity(subject, name)` as a domain dataclass in `backend/domain/models.py`.
- `backend/identity/google.py`:
  - `GoogleProvider(issuer, client_id, client_secret, redirect_uri, http)`: discovery, `/token` with Basic auth and `code_verifier`, and JWKS cached for 1 hour with one refetch on an unknown `kid`;
  - joserfc checks: RS256 only, plus `iss`, `aud`, `exp`, `iat` within 5 minutes of skew, and `nonce`;
  - a 5 s timeout on every call.
- `backend/identity/pkce.py`: verifier and S256 challenge.
- `backend/identity/config.py`:
  - reads the `TRIP_GOOGLE_*` and `TRIP_PUBLIC_URL` variables;
  - with no Google variables it returns `None`;
  - with only some set, it warns and names the missing one;
  - it refuses a non-local `http://` issuer.
- import-linter:
  - the layers contract becomes `main → api → services → (storage | identity) → domain`;
  - new forbidden contract: only `backend.identity` imports `httpx2` and `joserfc`;
  - existing contract: `backend.identity` may not import `fastapi`, `starlette` or `uvicorn`.
- `e2e/fake_google.py`, a small FastAPI app:
  - discovery, JWKS, and `/authorize`, a page with Subject and Name fields and **Continue** and **Cancel** buttons;
  - `/token`, which checks the client, the code, the redirect URI and the PKCE verifier;
  - codes are single-use and kept in memory.
  `e2e/conftest.py` starts it on port 8102. Nothing uses it yet.

Success criteria:
- [x] Unit tests (`backend/tests/unit/test_identity.py`):
  - the authorization URL has every parameter the spec lists;
  - the PKCE challenge matches the RFC 7636 appendix B example;
  - a valid token returns `Identity(subject, name)`;
  - each of a bad signature, the wrong `iss`, the wrong `aud`, an expired token, the wrong `nonce` and an `alg: none` token raises `IdentityRejected`;
  - a timeout, a `500`, or non-JSON from discovery, the token endpoint or JWKS raises `ProviderUnavailable`;
  - JWKS is fetched once per hour, and refetched once on an unknown `kid`.
- [x] Unit tests (`backend/tests/unit/test_identity_config.py`):
  - no variables gives `None`;
  - only an ID gives `None` and a WARNING naming `TRIP_GOOGLE_CLIENT_SECRET` but not the ID's value;
  - an `http://example.com` issuer raises;
  - `http://127.0.0.1:8102` is accepted.
- [x] Unit test (`backend/tests/unit/test_identity.py::test_never_logs_tokens_or_codes`): with `caplog`, no log record contains the code, ID token, client secret or subject.
- [x] Negative proof: temporarily `import httpx2` in `backend/services/auth.py`, then run `npm run check -- architecture`. It must fail on the new contract while the layers contract passes. Then revert. *Done in `backend/services/identity_port.py` (auth.py comes in Phase 2): "Only identity talks to the identity provider BROKEN", the other 3 kept; after the revert, 4 kept.*
- [x] `uv run pyright` reports 0 errors with joserfc and httpx2, and no suppressions were added (`rg "pyright: ignore|type: ignore|noqa" backend e2e` finds nothing new).
- [x] `npm run check` passes, and pip-audit is clean. *`lint unit architecture security` pass (integration and functional are untouched by this phase). pip-audit first flagged CVE-2026-126360 in `opentelemetry-api` 1.45.1, a FastAPI dependency already on `main`; the lock moves it to the fixed 1.45.2.*

Deviations: PKCE lives in `backend/domain/pkce.py` and the two provider errors in `backend/domain/errors.py`, because services generate the verifier and the adapter (below services) raises the errors. The adapter is `backend/identity/oidc.py` (`OidcProvider`), since nothing in it is Google-specific beyond the default issuer. The fake E2E provider moves to Phase 3, where it's first used, so it isn't untested code in between.

## Phase 2: SSO registration and sign-in API

- `storage`:
  - new tables and the `mobile` column (nullable for now, see Human attention);
  - `identities` lookups;
  - add and consume flows and pending registrations, deleting expired rows when a new flow starts;
  - counts for the 1,000 caps.
- `services/auth.py`:
  - `start_sign_in`, `finish_sign_in` (four outcomes), `pending_registration` and `complete_registration`;
  - a `return_to` allow-list: starts with a single `/`, has no `\`, no `//` and no scheme, and is at most 200 characters, otherwise `/`;
  - INFO logs with the provider, the outcome and the user ID only.
- `backend/api/auth.py`:
  - the routes in the API table above, and the flow and pending-registration cookies;
  - the callback catches every service failure, including `StorageUnavailable`, and redirects to `/?sign_in=failed`;
  - `code` and `state` over 512 characters fail straight away.
- `backend/api/schemas.py`: `Mobile`. Spaces and hyphens are removed first, the raw input is at most 20 characters, and the result must match `^\+[1-9][0-9]{7,14}$`. `Registration` is `{user_id, display_name, mobile}`, and `MemberResponse` gains `mobile`.
- `main.py`: builds `GoogleProvider` from the config, or `None`, and keeps it on `app.state`. A `get_identity_provider` dependency answers `404` when it's `None`. Integration tests override it with `FakeIdentityProvider`.
- The old `POST /api/members` and `POST /api/sign-in` are left alone.

Success criteria:
- [x] Integration tests (`backend/tests/integration/test_auth.py`) with `FakeIdentityProvider` and the injected clock:
  - start → `302` with the right `Location`, and a flow cookie with `HttpOnly`, `SameSite=Lax` and `Path=/api/auth`;
  - a callback for a linked subject → a `302` to `return_to` with a `session` cookie that `GET /api/me` accepts;
  - a callback for a new subject → a `302` to `/register/complete` with a pending-registration cookie (`Strict`), and no member or session created;
  - `GET /api/auth/registration` returns the name suggestion and `return_to`;
  - `POST` creates a linked member and a session.
- [x] Integration tests, failures. Each of these redirects to `/?sign_in=failed` with no `session` cookie:
  - a wrong `state`, a reused `state`, no flow cookie, a flow 10 minutes 1 second old;
  - `IdentityRejected`, `ProviderUnavailable`;
  - a 513-character `code`, the 1,001st open flow, a corrupted database.

  `error=access_denied` → `/?sign_in=cancelled`.
- [x] Integration tests, `return_to`: `/groups/7` is kept; `https://evil.example`, `//evil.example`, `/\evil` and a 201-character path each become `/`. *Also a tab inside the path (browsers drop it, turning `/<tab>/host` into `//host`), `javascript:`, a relative path and an empty value.*
- [x] Integration tests, registration:
  - a taken user ID → `409 User ID already taken`, and the pending registration still works afterwards;
  - bad user IDs, display names and mobiles (`09876543210`, `+0123456789`, `+91abc`, 7 and 16 digits, a 21-character raw input), a missing field, an unknown field → `422 {"detail": "Invalid request"}`, and the body doesn't contain the input;
  - `+91 98765-43210` is stored as `+919876543210`;
  - two members with the same mobile → both `201`;
  - no, an expired or a used pending registration → `401 Not signed in`;
  - a subject linked meanwhile → `409 Account already linked`;
  - two threads submitting on a `threading.Barrier` → exactly one member.
- [x] Integration tests, unconfigured provider: `/api/auth/providers` → `{"providers": []}`, and start, callback and registration → `404`.
- [x] Integration test: the database has no column holding an email, token or Google name, and `identities` holds only `provider`, `subject` and `user_id` (inspected through `sqlite3`).
- [x] Unit tests (`backend/tests/unit/test_auth_service.py`) cover the outcomes, the `return_to` rule, expiry, the caps and single use against a `tmp_path` database. A `caplog` test shows no log record contains a display name, mobile, code, state, nonce or subject. Backend unit coverage stays at 80% or more. *90%.*
- [x] `npm run check` passes. The old frontend and E2E still use the old routes and are untouched. *All stages pass. The old routes now return `mobile: null`, so the two old inside tests that pin those bodies exactly (`test_register_sends_one_request`, `test_sign_in_sends_one_request_and_never_resends_the_password`) and three old integration assertions in `test_members.py` gained `"mobile": None`. All of them are removed in Phase 3.*

## Phase 3: Google sign-in in the app, retire the old forms

- Backend:
  - remove `POST /api/members` and `POST /api/sign-in`, the `Registration`, `SignIn` and `Password` models, and their tests;
  - `mobile` becomes `NOT NULL`;
  - add the old-database check at startup.
- `frontend/src/api.ts`:
  - remove `register` and `signIn`;
  - add `getProviders`, `getPendingRegistration` and `completeRegistration`;
  - `Member` gains `mobile`;
  - `ConflictReason` gains `Account already linked`.
- `SignedOut.tsx` is rewritten:
  - the welcome panel, plus a **Continue with Google** link to `/api/auth/google/start?return_to=<current path>`, with the Google mark as an inline SVG in `ui/Icon.tsx`;
  - or "Sign-in isn't set up yet. See the README.";
  - reads `?sign_in=failed|cancelled|expired`, shows the matching message and removes the query with a `replace` navigation.
- New `FinishRegistration.tsx` at `/register/complete`, rendered while signed out:
  - the three fields with their rules shown up front;
  - "Group owners can see your mobile number.";
  - mobile checked first by `validation.ts` (`isValidMobile`, `MOBILE_HINT`);
  - on `201`, the member is signed in and the app goes to `return_to`;
  - on `401`, the app goes to `/?sign_in=expired`.
- `e2e/conftest.py`:
  - starts the fake provider for both server pairs;
  - sets `TRIP_GOOGLE_CLIENT_ID`, the per-session secret, `TRIP_GOOGLE_ISSUER` and `TRIP_PUBLIC_URL` for each backend;
  - allows the fake origin in `traffic`.
- `e2e/app.py`:
  - `sign_up(page, user_id, name, mobile)` and `sign_in_with_google(page, subject)` click through the fake provider page;
  - `register_and_sign_in` is rebuilt on them, so the group journeys keep working unchanged;
  - `test_screenshots.py`'s `showcase` signs Ada and Bob up through the same flow with `APIRequestContext`, without following redirects.
- Replaced E2E tests:
  - outside: `test_shows_sign_in_and_register_forms`, `test_register_sign_in_and_see_display_name`, `test_unregistered_user_id_cannot_sign_in`, `test_taken_user_id_cannot_register_again`, `test_markup_in_a_display_name_is_never_rendered`, `test_welcome_panel_sits_beside_the_forms_wide_and_above_them_narrow`;
  - inside: `test_register_sends_one_request`, `test_sign_in_sends_one_request_and_never_resends_the_password`, `test_unregistered_sign_in_gets_generic_401`, `test_taken_user_id_gets_one_generic_409`, `test_markup_display_name_is_refused_before_any_request`.

  Their replacements are in the coverage table.

Success criteria:
- [x] Vitest:
  - signed-out shows **Continue with Google** with an `href` that carries `return_to`, and no textbox or password field;
  - no providers shows the not-set-up text;
  - each `sign_in` value shows its message, and the address loses the query;
  - Finish registering prefills the name, refuses bad input with no request sent, sends one request on a double click, keeps the input on `409`, and goes to `return_to` on `201`;
  - markup in a suggested name renders as text.
- [x] E2E outside, through the fake provider:
  - a new person signs up and lands home signed in;
  - a returning person signs in;
  - a person signed out at `/groups/<id>` lands back there;
  - cancel shows "Sign-in was cancelled.";
  - a taken user ID shows the message and keeps the input;
  - a callback replayed in a second context fails;
  - sign-out shows **Continue with Google** again.
- [x] E2E inside:
  - a signed-out load makes exactly `GET /api/me` (401) then `GET /api/auth/providers`;
  - sign-up makes `GET /api/auth/google/start` (302), the fake provider pages, `GET /api/auth/google/callback` (302), `GET /api/auth/registration` and `POST /api/auth/registration` (201);
  - no `Location` the backend sends contains `code`, `state` or `id_token` except the one to the provider;
  - no API body contains the subject.
- [x] Every existing group journey and inside test passes unchanged on the new sign-up helper. *69 E2E tests pass. The inside tests that pinned the whole call list from page load now start from the sign-up sequence; sign-out now also loads the providers list.*
- [x] Unit test (`backend/tests/unit/test_storage.py::test_old_database_stops_startup`): a database with the old `members` table raises the "Delete trip.db" error. *Also checked on a copy of the repo's real old `trip.db`. The check runs before `create_all`, so an old file isn't modified.*
- [x] `rg "api/members|api/sign-in|Passwords aren" backend frontend/src e2e` finds nothing, and `create_app().openapi()` lists neither route. *The only matches are `test_retired_routes_create_nothing` and `test_create_app_registers_api_routes`, which assert the routes are gone.*
- [x] Browser check with the Playwright MCP server against `npm run dev`, with Google not configured: the signed-out screen shows the not-set-up message. (The real-Google check is the human's manual DoD item.) *At `/groups/7?sign_in=cancelled` on a scratch database: "Sign-in isn't set up yet. See the README.", "Sign-in was cancelled.", and the address became `/groups/7`. Console: only the expected 401s from the session check.*

Deviations:
- The Google mark is its own component, `frontend/src/ui/GoogleMark.tsx`, coloured through four new tokens in `tokens.css` (so the raw-colour scan still holds), rather than an entry in `ui/Icon.tsx`, whose icons are single-colour strokes.
- The fake provider (`e2e/fake_google.py`) lands here instead of Phase 1, and `ApiTraffic.foreign_origins` now takes several allowed origins.
- `docs/plans/PLAN_app-shell-and-design-system.md` (Done) named five vitest titles and one journey that this phase retired; its coverage rows now name the replacements, with a note, so `scripts/harness-config.test.mjs` keeps passing.
- [x] `npm run check` passes. *All 7 stages: 147 unit (backend), 244 vitest, 151 integration, 69 E2E.*

## Phase 4: Name, @user-id and mobile visibility

- `services/groups.py`:
  - `group_detail` adds `user_id` to members and requests, plus `mobile` only when the viewer is the owner;
  - the rule is in `can_see_mobile(viewer, group)`, applied by the service, never by the API;
  - group summaries gain `owner_user_id`.
- `schemas.py`: the `members` and `pending_requests` items gain `user_id` and an optional `mobile`, left out of the JSON when absent (`exclude_none` on those models only). `GroupResponse` gains `owner_user_id`.
- Frontend:
  - the banner shows the Name, with `@user_id` beneath in a muted token that passes the contrast test;
  - cards read "by {name} (@{id})";
  - group members and requests show `@id`;
  - for the owner, a `tel:` link that's at least 44 px tall on phones;
  - Approve and Reject `aria-label`s read "Approve Ada Lovelace (@ada)".

Success criteria:
- [x] Integration tests (`test_groups.py`):
  - the owner's detail has `mobile` for each member and requester;
  - a member's detail, a non-member's detail, browse, my-groups and join-request responses contain no `mobile` key anywhere (a recursive key search);
  - every summary has `owner_user_id`.
- [x] Unit tests (`test_groups_service.py`): `can_see_mobile` for owner, member, requester and stranger. *`test_only_the_owner_sees_mobile_numbers`; the rule is `can_see_mobiles(viewer_status)` in `backend/domain/models.py`, applied in `services/groups.py::group_detail`.*
- [x] Vitest: the banner shows the name and `@ada`; the cards show `(@ada)`; owner rows have `tel:+919876543210` links and the buttons are labelled with the name and ID; a member's view has no `tel:` link; two "Ada"s are told apart by `@id`.
- [x] `frontend/src/theme/tokens.test.ts` still passes with the muted `@id` colour in both themes. *`@id` uses the existing `--color-text-muted`, already in the contrast pairs on `--color-bg` and `--color-surface`; no new colour.*
- [x] E2E outside: the owner sees the requester's `@id` and phone link, and the requester, once a member, sees `@id` but no phone link. E2E inside: the member's `GET /api/groups/<id>` body has no `mobile`.

Deviations: people in group detail are a new domain type, `Person(user_id, display_name, mobile | None)`, and `PendingRequest` carries one as `requester`. `mobile` is left out of the JSON with pydantic's field-level `exclude_if` (pydantic 2.14), because `exclude_none` on the route would also drop `members: null`. The shared rendering is `frontend/src/ui/PersonDetails.tsx`; phone links are labelled "Call Ada (@ada) on +91…".
- [x] `npm run check` passes. *All 7 stages: 151 backend unit (90% coverage), 251 vitest, 156 integration, 71 E2E.*

## Phase 5: Profile editing, screenshots and docs

- `services/members.py`: `update_profile(member, display_name, mobile)` in one transaction, logging `profile updated user_id=… fields=mobile,display_name` with no values. `POST /api/me/profile` uses a `ProfileUpdate` model (`extra="forbid"`, both fields required).
- `Profile.tsx` at `/profile`:
  - the title "Profile · Caravan" and a **Back to groups** link;
  - the user ID as read-only text, and the Display name and Mobile number inputs;
  - the owner-visibility note, and **Save** that's disabled while in flight;
  - "Profile saved." with `role="status"`; on `401`, the sign-in screen.

  The banner gets a **Profile** link, and after saving the banner updates from the response.
- Screenshots: `profile` is added to `SCREENS` in `e2e/test_screenshots.py` and `scripts/screenshot-summary.mjs`, and every place that names 20 becomes 24 (list under Human attention).
- Docs:
  - `docs/SPEC.md`: auth, API table, mobile rules and visibility, `@id` display, profile, and the revised local-use warning;
  - `docs/STATUS.md`;
  - `docs/TECH_STACK.md`: joserfc, httpx2 at runtime, the identity layer, and the environment variables;
  - `README.md`: setting up a Google OAuth client with redirect URI `http://localhost:5173/api/auth/google/callback`, the variable names, and deleting `trip.db`;
  - `docs/PROCESS.md`.

Success criteria:
- [ ] Integration tests (`backend/tests/integration/test_profile.py`):
  - a mobile change → `200` with the normalized number, and `GET /api/me` shows it;
  - the owner's group detail then shows the new number, and the old one is in no table;
  - a display-name change shows in the owner's detail, while the user ID, memberships, pending requests and session are unchanged;
  - bad values, an unknown field, a `user_id` in the body, and a 5 KB body → `422` or `413`, with nothing changed;
  - unchanged values → `200`, the same;
  - no session → `401`;
  - two concurrent saves on a `Barrier` → one of the two complete profiles, never a mix.
- [ ] Unit test (`test_members_service.py::test_profile_update_logs_fields_not_values`): the log names the changed fields, and contains neither the old nor the new values.
- [ ] Vitest (`Profile.test.tsx`):
  - shows the user ID as text, not an input, and fills the current values;
  - a bad mobile is refused with no request sent;
  - a double click sends one request;
  - success shows "Profile saved." and updates the banner name;
  - `401` returns to sign-in at `/profile`.
- [ ] E2E outside: change the mobile number on Profile, and the owner sees the new number on the group. E2E inside: Save makes exactly one `POST /api/me/profile` (200).
- [ ] `node --test scripts/screenshot-summary.test.mjs scripts/open-pr.test.mjs` passes with 24, and `npm run check -- functional` writes exactly 24 files to `test-results/screenshots/`.
- [ ] Browser check with the Playwright MCP server against `npm run dev` at 360 px and 1280 px: Profile shows no sideways scroll, and Save works by keyboard alone.
- [ ] Docs updated, and `rg -n "\b20\b (screenshots|captures)" docs/PROCESS.md docs/STATUS.md README.md .claude scripts` finds nothing.
- [ ] `npm run check` passes.

## Final verification

- [ ] `npm run check` passes
- [ ] Every acceptance criterion in the spec is covered by a test (table below)
- [ ] `code-reviewer` and `security-reviewer` run before `/ship` (left for `/ship`)
- [ ] The human signs in once with a real Google account on `localhost` (manual, spec Definition of Done)

### Spec coverage

| Spec acceptance criterion | Tests |
|---|---|
| Configured, no session: Continue with Google, no user-ID or password fields | `frontend/src/SignedOut.test.tsx::shows Continue with Google and no user ID or password fields`, `e2e/test_journeys.py::test_signed_out_screen_offers_only_google` |
| Not configured: not-set-up message, start returns 404 | `frontend/src/SignedOut.test.tsx::says sign-in isn't set up when no provider is configured`, `backend/tests/integration/test_auth.py::test_unconfigured_provider_routes_are_not_found` |
| Retired endpoints create no member or session | `backend/tests/integration/test_auth.py::test_retired_routes_create_nothing` |
| Start redirects to Google with every parameter and sets the flow cookie | `backend/tests/integration/test_auth.py::test_start_redirects_with_pkce_state_and_nonce`, `backend/tests/unit/test_identity.py::test_authorization_url_has_every_parameter`, `e2e/test_network_contract.py::test_sign_up_follows_the_redirects_once` |
| `return_to` kept for `/groups/7`, ignored when not an app path | `backend/tests/integration/test_auth.py::test_return_to_keeps_an_app_path`, `backend/tests/integration/test_auth.py::test_return_to_ignores_anything_else`, `e2e/test_journeys.py::test_signed_out_visitor_lands_on_the_group_after_signing_in` |
| Linked subject: code exchanged with verifier, session started, flow cookie cleared, redirect to `return_to` | `backend/tests/integration/test_auth.py::test_callback_signs_in_a_linked_member`, `backend/tests/unit/test_identity.py::test_token_request_sends_the_code_verifier` |
| After the redirect, `/api/me` returns the member and the banner shows name and @id | `e2e/test_journeys.py::test_returning_member_signs_in_with_google`, `frontend/src/App.test.tsx::shows the display name with the user ID beneath` |
| Bad signature, `iss`, `aud`, `exp` or `nonce` → no session, `/?sign_in=failed` | `backend/tests/unit/test_identity.py::test_rejects_tokens_that_fail_any_check`, `backend/tests/integration/test_auth.py::test_rejected_identity_redirects_to_failed` |
| Missing, unknown, reused, expired state or no flow cookie → failed, no code exchanged | `backend/tests/integration/test_auth.py::test_bad_state_never_exchanges_the_code`, `e2e/test_journeys.py::test_replayed_callback_in_another_browser_fails` |
| Cancel at Google → `/?sign_in=cancelled` and message | `backend/tests/integration/test_auth.py::test_access_denied_redirects_to_cancelled`, `e2e/test_journeys.py::test_cancelling_at_google_says_so` |
| `/?sign_in=failed` shows the message and the query is removed | `frontend/src/SignedOut.test.tsx::shows the %s message and removes the query` |
| New subject: no member or session yet, redirect to `/register/complete`, pending cookie | `backend/tests/integration/test_auth.py::test_callback_for_a_new_subject_starts_a_pending_registration` |
| Finish registering form: three fields, name prefilled only when valid | `frontend/src/FinishRegistration.test.tsx::prefills a valid Google name and leaves an invalid one empty`, `backend/tests/integration/test_auth.py::test_pending_registration_suggests_only_a_valid_name` |
| Valid submit creates a linked member and session, returns 201, lands on `return_to` | `backend/tests/integration/test_auth.py::test_completing_registration_creates_a_linked_member`, `e2e/test_journeys.py::test_new_person_signs_up_with_google`, `e2e/test_network_contract.py::test_sign_up_follows_the_redirects_once` |
| Taken user ID → 409, input kept, pending still usable | `backend/tests/integration/test_auth.py::test_taken_user_id_keeps_the_pending_registration`, `e2e/test_journeys.py::test_taken_user_id_says_so_and_keeps_the_input` |
| Invalid user ID, name or mobile → 422, field marked | `backend/tests/integration/test_auth.py::test_invalid_registration_is_refused`, `frontend/src/FinishRegistration.test.tsx::marks the %s field and sends nothing` |
| No, expired or used pending registration → 401 and the expired message | `backend/tests/integration/test_auth.py::test_missing_or_used_pending_registration_is_401`, `frontend/src/FinishRegistration.test.tsx::returns to sign-in with the expired message on 401` |
| Subject linked meanwhile → 409 Account already linked, no second member | `backend/tests/integration/test_auth.py::test_subject_linked_meanwhile_is_409`, `backend/tests/integration/test_auth.py::test_concurrent_registrations_create_one_member` |
| Mobile with spaces or hyphens is stored without them | `backend/tests/integration/test_auth.py::test_mobile_is_stored_without_spaces_or_hyphens` |
| Badly formed mobile → 422 and the hint | `backend/tests/integration/test_auth.py::test_invalid_mobile_is_refused`, `frontend/src/FinishRegistration.test.tsx::shows the mobile hint for %s` |
| Same mobile for two members is allowed | `backend/tests/integration/test_auth.py::test_two_members_may_share_a_mobile` |
| Owner sees members' and requesters' mobiles as `tel:` links | `backend/tests/integration/test_groups.py::test_owner_sees_mobiles_of_members_and_requesters`, `frontend/src/Groups.test.tsx::the owner sees phone links for members and requests`, `e2e/test_journeys.py::test_owner_sees_the_requesters_user_id_and_phone` |
| Non-owner member sees no mobiles and no `mobile` field | `backend/tests/integration/test_groups.py::test_members_never_receive_a_mobile`, `frontend/src/Groups.test.tsx::a member sees no phone links`, `e2e/test_network_contract.py::test_member_group_detail_has_no_mobile` |
| Browse, my-groups and join-request responses contain no mobile | `backend/tests/integration/test_groups.py::test_lists_and_requests_never_contain_a_mobile` |
| The member sees their own user ID, name and mobile on their profile | `frontend/src/Profile.test.tsx::shows the user ID as text and fills the current values` |
| Profile link opens `/profile` with title, back link, read-only user ID, filled fields, note | `frontend/src/Profile.test.tsx::shows the user ID as text and fills the current values`, `frontend/src/App.test.tsx::the Profile link opens the profile screen`, `e2e/test_journeys.py::test_member_changes_their_mobile_number` |
| Saving a new mobile sends the POST, returns the normalized number, shows Profile saved | `backend/tests/integration/test_profile.py::test_changing_the_mobile_returns_it_normalized`, `frontend/src/Profile.test.tsx::shows Profile saved and updates the banner`, `e2e/test_network_contract.py::test_saving_the_profile_posts_once` |
| Owner sees the new number next time; the old one isn't stored | `backend/tests/integration/test_profile.py::test_owner_sees_the_new_mobile_and_the_old_one_is_gone`, `e2e/test_journeys.py::test_member_changes_their_mobile_number` |
| Changed display name shows everywhere; user ID, groups, requests and session unchanged | `backend/tests/integration/test_profile.py::test_changing_the_name_keeps_everything_else` |
| Invalid profile input: nothing sent, field marked, text kept; server 422 changes nothing | `frontend/src/Profile.test.tsx::refuses %s without sending a request`, `backend/tests/integration/test_profile.py::test_invalid_profile_changes_nothing` |
| `user_id` or unknown field in the body → 422, nothing changed | `backend/tests/integration/test_profile.py::test_user_id_cannot_be_changed` |
| Unchanged values → 200 with the same profile | `backend/tests/integration/test_profile.py::test_saving_unchanged_values_is_idempotent` |
| No session: signed-out screen, 401, back on `/profile` after signing in | `backend/tests/integration/test_profile.py::test_profile_needs_a_session`, `frontend/src/Profile.test.tsx::returns to sign-in at the same address on 401` |
| Double click on Save sends one request | `frontend/src/Profile.test.tsx::a double click sends one request` |
| Banner shows name with @id beneath, initials from the name | `frontend/src/App.test.tsx::shows the display name with the user ID beneath` |
| Member list and requests show name and @id; buttons labelled with both | `frontend/src/Groups.test.tsx::people show their user ID beside their name`, `e2e/test_journeys.py::test_owner_sees_the_requesters_user_id_and_phone` |
| Cards show the owner as "by name (@id)" | `frontend/src/Groups.test.tsx::cards show the owner's name and user ID` |
| Two members named Ada are told apart by @id | `frontend/src/Groups.test.tsx::two people with the same name are told apart by user ID` |
| API shapes: members, pending requests, `owner_user_id` | `backend/tests/integration/test_groups.py::test_people_carry_their_user_id`, `backend/tests/integration/test_groups.py::test_groups_carry_the_owner_user_id` |
| Same email, different subjects → two members | `backend/tests/integration/test_auth.py::test_same_email_different_subjects_are_two_members` |
| Database holds separate columns and only provider and subject for the link | `backend/tests/integration/test_auth.py::test_stores_no_email_name_or_tokens` |
| Logs carry the user ID only, never personal data or flow secrets | `backend/tests/unit/test_auth_service.py::test_logs_carry_only_the_user_id`, `backend/tests/unit/test_identity.py::test_never_logs_tokens_or_codes`, `backend/tests/unit/test_members_service.py::test_profile_update_logs_fields_not_values` |
| Sign-out ends the session and shows Continue with Google | `e2e/test_journeys.py::test_sign_out_returns_to_sign_in`, `e2e/test_network_contract.py::test_sign_out_sends_one_request` |
