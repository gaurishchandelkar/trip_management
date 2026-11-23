# Spec: Registration and sign-in with Google

> Status: **draft, decisions confirmed** (D1–D10 at the end, 2026-11-23). Next: `/plan sso-registration`.

## Expected outcome

Friends register for Caravan and sign in with their Google account instead of a user ID and an
unchecked password. On first sign-in they pick a user ID, a display name and their mobile number;
after that, Google alone signs them in. The user ID (login ID) and the display name (Name) are
stored separately and each has one job: the Name is what people read, and `@user-id` tells two
people with the same Name apart. Group owners can see the mobile numbers of their members and
requesters. A signed-in member can edit their profile at any time to change their mobile number or
display name; the user ID never changes. The user-ID sign-in and registration forms are retired, and existing local members are
discarded (fresh start).

## Constraints

- `/api/health`, `/api/sign-out`, every join-request endpoint and their error bodies are unchanged. Responses that carry people only **gain** fields (listed under Acceptance criteria); no existing field is renamed or removed, so the frontend can move over one screen at a time.
- **Retired (D2):** `POST /api/members` and `POST /api/sign-in`, the **Sign in** and **Register** forms, the "Passwords aren't checked yet." note, and their unit, integration and E2E tests. Both routes return `404` (or `405`) afterwards, like any unknown route.
- **Fresh start (D2):** existing data is not migrated. `README.md` tells the human to delete their local `trip.db`. A member row without a Google link can never sign in.
- **Identity fields stay separate (D9):** `user_id` stays the primary key and the only thing other tables, sessions and logs refer to. `display_name` is stored in its own column and is never used as a key, never used to look a member up, and never written to logs. `mobile` is a third, separate column. None of the three is derived from another.
- The session stays as it is: a random token whose SHA-256 hash is stored, sent as the `session` cookie (`HttpOnly`, `SameSite=Strict`, `Path=/api`), lasting 7 days. Google sign-in creates exactly this kind of session, so the rest of the app can't tell how a member signed in.
- User ID and display-name rules are unchanged (D8: a single display name, as today), and user IDs stay unique and case-insensitive.
- The layer order stays `api` → `services` → `storage` → `domain`. Talking to Google (HTTP, token checks) lives behind a port the services call, so `domain` stays free of HTTP and crypto libraries and services can be tested with a fake provider. joserfc and httpx2 are used only in that adapter.
- Who may see a mobile number is decided in the service layer, from the session's member, never from the request.
- The Google client ID and secret come only from environment variables (`TRIP_GOOGLE_CLIENT_ID`, `TRIP_GOOGLE_CLIENT_SECRET`) that the human sets. Agents never read or write `.env*`, and the human adds the names to `.env.example`. No real or fixed credential is committed.
- The issuer defaults to `https://accounts.google.com`. Tests may override it (`TRIP_GOOGLE_ISSUER`) only with an `http://127.0.0.1` or `http://localhost` address; any other non-`https` issuer is refused at startup.
- Tests never contact Google. Integration and E2E tests use a local fake OpenID Connect provider on `127.0.0.1`, started by the test harness on its own port. The E2E rule that fails on any third-party request stays as it is, and the fake provider counts as a local origin only through explicit configuration in `e2e/`.
- With Google not configured, the app still starts. The signed-out screen says "Sign-in isn't set up yet. See the README." and the auth routes return `404`. `npm run check` and CI need no real secrets.
- The schema is still created on startup with no migrations. The `members` table gains a `mobile` column and new tables are added; that is safe only because of the fresh start.
- Mobile numbers are checked with a pattern, with no new dependency (no `phonenumbers`, no SMS provider).
- `e2e/test_screenshots.py` keeps its existing captures and adds the **Profile** screen in the same 4 variants (light and dark, 360 and 1280 px), 24 in all. The expected count is updated wherever the screenshot scripts pin it, and the "refuse a partial or stale set" check stays. The sign-in capture shows the new signed-out screen, signed-in captures sign in through the fake provider, and sample data uses fictional numbers.
- State-changing requests stay `POST` only, so the profile is saved with `POST`, not `PATCH` or `PUT`.
- Nothing binds to `0.0.0.0`. The only new runtime dependencies are joserfc and httpx2 (D4).
- Coverage gates stay at 80%. Every journey gets an outside E2E test and an inside network-contract test.

## Acceptance criteria

### Signed-out screen

- [ ] Given Google is configured and no session, when any address loads, then the welcome panel shows a **Continue with Google** button and no user-ID or password fields
- [ ] Given Google isn't configured, when the signed-out screen loads, then it shows "Sign-in isn't set up yet. See the README." and no button, and `GET /api/auth/google/start` returns `404 {"detail": "Not found"}`
- [ ] Given the retired endpoints, when `POST /api/members` or `POST /api/sign-in` is called, then no member or session is created

### Starting a sign-in

- [ ] Given Google is configured, when the person presses **Continue with Google**, then the browser goes to `GET /api/auth/google/start`, which redirects (`302`) to Google's authorization endpoint with `response_type=code`, the configured `client_id` and `redirect_uri`, `scope=openid profile email`, a fresh random `state`, a fresh random `nonce`, and a PKCE `code_challenge` with `code_challenge_method=S256`, and sets a flow cookie
- [ ] Given the person was at `/groups/7` when signed out, when the flow later succeeds, then they land on `/groups/7`; given a `return_to` that isn't a path inside the app (`https://evil.example`, `//evil.example`, `/\evil`, or anything over 200 characters), then it's ignored and they land on `/`

### Callback, returning member

- [ ] Given member `ada` is linked to Google subject `S1`, when Google redirects back with a valid `code` and the matching `state`, then the backend exchanges the code (sending the PKCE verifier), checks the ID token, starts a session for `ada`, sets the `session` cookie, clears the flow cookie and redirects to the saved `return_to`
- [ ] Given that redirect, when the app loads, then `GET /api/me` returns `200 {user_id: "ada", display_name: "Ada Lovelace", mobile: "+919876543210"}` and the banner shows "Signed in as Ada Lovelace" with "@ada" beneath
- [ ] Given an ID token whose signature, `iss`, `aud`, `exp` or `nonce` doesn't match, then no session is started and the browser is redirected to `/?sign_in=failed`
- [ ] Given a callback whose `state` is missing, unknown, already used, older than 10 minutes, or arrives without the matching flow cookie (for example opened in another browser), then no code is exchanged, no session is started, and the browser is redirected to `/?sign_in=failed`
- [ ] Given the person cancels at Google (callback carries `error=access_denied`), then the browser is redirected to `/?sign_in=cancelled` and the signed-out screen says "Sign-in was cancelled."
- [ ] Given `/?sign_in=failed`, then the signed-out screen says "Couldn't sign in with Google. Please try again." and the query is removed from the address bar

### Callback, new person (registration)

- [ ] Given no member is linked to Google subject `S2`, when the callback succeeds, then no member and no session are created yet; the browser is redirected to `/register/complete`, and a pending-registration cookie (10 minutes, `HttpOnly`, `SameSite=Strict`, `Path=/api`) is set
- [ ] Given a pending registration, when `/register/complete` loads, then it calls `GET /api/auth/registration` and shows a **Finish registering** form with three labelled fields, each with its rule shown up front: **User ID** (empty), **Display name** (prefilled from Google's `name` claim only if it passes the display-name rule, D5) and **Mobile number** (empty, `type="tel"`, `autocomplete="tel"`)
- [ ] Given a pending registration, when the person submits a valid, free user ID, a valid display name and a valid mobile number to `POST /api/auth/registration` `{user_id, display_name, mobile}`, then the member is created with each value in its own column and linked to subject `S2`, a session is started, `201 {user_id, display_name, mobile}` is returned with the session cookie, the pending registration is used up, and the app lands on the saved `return_to`
- [ ] Given a taken user ID, when the person finishes registering, then `409 {"detail": "User ID already taken"}` is returned, the form keeps their input, and the pending registration is still usable
- [ ] Given an invalid or missing user ID, display name or mobile number, when the person finishes registering, then `422 {"detail": "Invalid request"}` is returned (the frontend checks first and marks the failing field with its hint)
- [ ] Given no pending registration, or one that is expired or used, when `/api/auth/registration` is called, then `401 {"detail": "Not signed in"}` is returned and the app shows the signed-out screen with "Your sign-in expired. Please start again."
- [ ] Given subject `S2` became linked meanwhile (for example a second tab finished first), when the person finishes registering, then `409 {"detail": "Account already linked"}` is returned and no second member is created

### Mobile number (D6, D7)

- [ ] Given a mobile number in international format with spaces or hyphens (`+91 98765-43210`), when registering, then it is stored and returned without them (`+919876543210`)
- [ ] Given a mobile number without a leading `+` and country code (`09876543210`), with letters, with fewer than 8 or more than 15 digits, with a leading `0` after the `+`, or with any other character, then `422 {"detail": "Invalid request"}` is returned and the form says "Enter your mobile number with the country code, for example +91 98765 43210."
- [ ] Given two members who register the same mobile number (a shared family phone), then both registrations succeed; mobile numbers are not unique
- [ ] Given the owner of group G, when they open G, then each member and each pending requester is listed with their mobile number as a `tel:` link
- [ ] Given a member of G who isn't its owner, when they open G, then the member list has no mobile numbers, and `GET /api/groups/{id}` contains no `mobile` field anywhere in its body
- [ ] Given any browse, my-groups or join-request response, then it contains no mobile number
### Editing the profile (D10)

- [ ] Given a signed-in member, when they press **Profile** in the banner, then the app goes to `/profile` (tab title "Profile · Caravan") with a **Back to groups** link and an **Edit profile** form: User ID shown as read-only text ("@ada", not an input), and **Display name** and **Mobile number** inputs filled with their current values, each with its rule shown up front, and the note "Group owners can see your mobile number."
- [ ] Given the form, when the member changes the mobile number to `+44 7700 900123` and presses **Save**, then `POST /api/me/profile` `{display_name, mobile}` is sent, `200 {user_id, display_name, mobile: "+447700900123"}` is returned, the form shows "Profile saved." with `role="status"`, and the next `GET /api/me` returns the new number
- [ ] Given a member changed their mobile number, when the owner of a group they're in next opens that group, then the owner sees the new number, and the old one isn't stored anywhere
- [ ] Given the form, when the member changes the display name and saves, then the banner, and every group list and request that shows them, use the new name from then on; their user ID, groups, memberships, pending requests and session are unchanged
- [ ] Given an invalid display name or mobile number, when the member presses **Save**, then nothing is sent, the field is marked invalid with its hint, and the typed text is kept; given the server still answers `422`, then the same happens and nothing is changed
- [ ] Given a body that includes `user_id` or any other unknown field, when `POST /api/me/profile` is called, then `422 {"detail": "Invalid request"}` is returned and nothing is changed (the user ID can't be changed)
- [ ] Given unchanged values, when the member presses **Save**, then `200` is returned with the same profile (saving is idempotent)
- [ ] Given no session, when `GET /profile` loads or `POST /api/me/profile` is called, then the app shows the signed-out screen (`401 {"detail": "Not signed in"}`), and after signing in the member lands back on `/profile`
- [ ] Given a double click on **Save**, then one request is sent (the button is disabled while it's in flight)

### Name and user ID across the app (D9)

The Name is what people read; `@user-id` sits beside it, smaller, so two people with the same Name can be told apart.

- [ ] Given a signed-in member, then the banner shows "Signed in as {display name}" with "@{user_id}" beneath, and the avatar's initials come from the display name
- [ ] Given a group's member list or pending requests, then each person shows their display name and "@{user_id}" beside it; the **Approve** and **Reject** buttons are labelled with the display name and user ID ("Approve Ada Lovelace (@ada)")
- [ ] Given the browse and my-groups cards, then the owner is shown as "by {owner display name} (@{owner user ID})"
- [ ] Given two members both named "Ada", when they're in the same group, then the owner can tell their requests apart by `@user-id`
- [ ] Given the API, then `members` entries are `{user_id, display_name}` (plus `mobile` for the owner), `pending_requests` entries are `{request_id, user_id, display_name}` (plus `mobile` for the owner), and `group` gains `owner_user_id`

### Accounts and privacy

- [ ] Given two different Google subjects with the same email address, then they become two separate members; accounts are never matched or merged by email (D3)
- [ ] Given any stored member, then the database holds their user ID, display name and mobile number in separate columns, and only the provider name and subject for their Google link, with no email, Google name, picture, access token or refresh token
- [ ] Given any sign-in, registration, profile change or group action, then log lines carry the user ID only (a profile change logs `profile updated user_id=…` and which fields changed, never their values), and never a display name, mobile number, code, token, `state`, `nonce`, subject or email

### Sign-out

- [ ] Given a member signed in through Google, when they sign out, then the session ends as today and the signed-out screen shows **Continue with Google** (the app doesn't sign them out of Google)

## Non-functional requirements

- **Security:**
  - OpenID Connect authorization-code flow with PKCE (`S256`), `state` and `nonce`, with the ID token checked by joserfc. The flow record (state hash, nonce, PKCE verifier, `return_to`) is stored server-side, is single-use and expires after 10 minutes.
  - The ID token is checked against Google's published keys (JWKS, cached), plus `iss`, `aud`, `exp`, `iat` and `nonce`. Endpoints come from configuration and discovery, never from the request.
  - The flow cookie carries a random flow ID to the callback. It must be `SameSite=Lax`, because the callback is a top-level navigation from Google, where a `Strict` cookie isn't sent. It is `HttpOnly`, `Path=/api/auth`, lives 10 minutes and is cleared on callback. The `session` and pending-registration cookies stay `Strict`.
  - The callback is a `GET` that changes state, the one exception to "state-changing requests are POST only". It's protected by `state`, the flow cookie and single use.
  - `return_to` is allow-listed to a relative path inside the app, so the flow can't become an open redirect. The callback's `Location` is always a same-origin path.
  - Each Google subject maps to at most one member, and each member has exactly one Google link (unique constraints in storage).
  - Mobile numbers are shown only to the member and to owners of a group the member belongs to or has a pending request for. The rule lives in one service function, with unit tests for owner, member, requester and stranger.
- **Privacy:** Google is asked for `openid profile email` only. The email isn't stored. The `name` claim lives only in the pending registration and is deleted with it. The mobile number is personal data: it's never logged, never in error bodies, never in URLs, and the registration form tells the person "Group owners can see your mobile number."
- **Accessibility:** **Continue with Google** is a real link styled as a button, at least 44 px tall on phones, with a visible label. The Google mark is an inline SVG from our own sources with `aria-hidden`, never loaded from Google. The **Finish registering** form follows today's form rules (visible labels, rules shown up front, `role="alert"` errors, disabled while in flight). `@user-id` labels meet WCAG AA contrast in both themes, and the `tel:` links are at least 44 px tall on phones.
- **Performance:** the callback finishes in under 2 seconds when Google answers quickly; Google calls time out after 5 seconds. JWKS is cached for 1 hour and refetched once on an unknown key ID. Adding `user_id` and `mobile` to group detail adds no extra queries per member.
- **Observability:** sign-in and registration outcomes are logged at INFO (`provider`, `outcome`, `user_id` when known). Google timeouts and token failures are logged at WARNING without token contents. A partly configured provider (ID without secret) logs a WARNING at startup naming the missing variable, not its value.
- **Cost:** no new infrastructure and no SMS provider. The human registers a free Google OAuth client with `http://localhost:5173/api/auth/google/callback` as an allowed redirect URI for development.

## Failure conditions

- **Invalid input** to `POST /api/auth/registration` (bad or missing user ID, display name or mobile number, unknown field, wrong type, body over 4 KB) → `422 {"detail": "Invalid request"}` or `413`, as today. The mobile number is checked after removing spaces and hyphens, against `^\+[1-9][0-9]{7,14}$`, and the raw input is at most 20 characters. Invalid callback parameters (missing `code` or `state`, or either over 512 characters) → redirect to `/?sign_in=failed`.
- **Google down, slow or erroring** (token endpoint, discovery or JWKS times out after 5 seconds, or answers non-2xx or malformed JSON) → no session, redirect to `/?sign_in=failed`, WARNING logged. Existing sessions keep working.
- **Not configured or misconfigured** → auth routes return `404`, and the signed-out screen says sign-in isn't set up. The app still starts. A non-local `http://` issuer stops startup with a clear error.
- **Old database** (a `trip.db` from before this change, without the `mobile` column or the new tables) → startup stops with a clear message telling the human to delete `trip.db`, rather than answering every request with `503`.
- **Replay and race:** a `state` and a pending registration can each be used once. A second callback with the same `state` fails; a double-submitted **Finish registering** creates one member, and the second submit gets `401` or `409`.
- **Time limits:** flows and pending registrations expire after 10 minutes. Expired records are deleted when the next flow starts.
- **Size limits:** at most 1,000 unexpired flow records and 1,000 pending registrations in total. Starting a flow past that redirects to `/?sign_in=failed`, so the tables can't grow without bound.
- **Profile edits:** invalid input, unknown fields or a body over 4 KB → `422` or `413` and nothing changes. Two tabs saving at once → each save is one transaction and the last one wins; neither leaves a half-updated profile. The profile is saved as a whole: both fields are required in every save.
- **Storage unavailable** → `503 {"detail": "Service unavailable"}` on JSON endpoints, or a redirect to `/?sign_in=failed` on start and callback; nothing half-written (each step is one transaction).

## Definition of Done

- [ ] All acceptance criteria are covered by passing tests (unit, integration with a fake OIDC provider, E2E outside and inside)
- [ ] The inside E2E tests check that no response to a non-owner contains a `mobile` field
- [ ] The retired forms, endpoints and their tests are removed, and the E2E journeys and screenshots sign in through the fake provider
- [ ] `npm run check` passes with no real Google credentials set
- [ ] `docs/SPEC.md`, `docs/STATUS.md` and `docs/TECH_STACK.md` are updated: new endpoints, tables and response fields, the mobile-number and visibility rules, the Name and `@user-id` display rule, the **Profile** screen and `POST /api/me/profile`, environment variable names, joserfc and httpx2, and the "Local and trusted use only" warning revised now that passwords are gone
- [ ] `uv.lock` is updated and pip-audit is clean
- [ ] `.env.example` lists the new variable names (added by the human)
- [ ] `README.md` explains how to register a Google OAuth client for local development and to delete the old `trip.db`
- [ ] The human has signed in with a real Google account once on `localhost` and confirmed it works (manual check, not in CI)
- [ ] `code-reviewer` and `security-reviewer` have run with no unresolved findings

## Out of scope

- Verifying mobile numbers (SMS one-time codes), SMS or WhatsApp messages of any kind, including when the number is changed
- Changing the user ID after registration
- A history of past mobile numbers or display names, or notifying owners when a number changes
- Asking Google to sign in again before a profile change
- Sharing mobile numbers with anyone but group owners, and per-member privacy settings
- Splitting the name into first and last, or a separate full name
- Providers other than Google (Microsoft, GitHub, Apple). The adapter is written for OpenID Connect so a later spec can add Microsoft through configuration and tests.
- Linking, unlinking or switching the Google account of a member, merging members, deleting an account
- Migrating existing members (fresh start)
- Email/password accounts, password reset, email verification
- Using Google access tokens for anything (contacts, calendar, profile pictures, phone number)
- Multi-factor authentication beyond what Google does
- Rate limiting by IP, CAPTCHA, deployment to a public host, HTTPS termination
- SAML or enterprise SSO

## Decisions

Confirmed by the human on 2026-11-23.

- **D1. Providers:** Google only, built on generic OpenID Connect so more providers can follow.
- **D2. Existing sign-in:** retired. Google is the only way to register and sign in. Existing members aren't migrated: fresh start, delete the local `trip.db`.
- **D3. Matching accounts:** never by email. One Google subject is one member. Because every member is created through Google, no linking step is needed.
- **D4. Dependency:** joserfc and httpx2 approved as runtime dependencies, used only in the OIDC adapter (`backend/identity/`). Amended at plan approval on 2026-11-23: Authlib was first approved, but its OAuth client fails `pyright --strict` without suppressions, while joserfc (Authlib's own typed JOSE library) passes. httpx2 was already locked as a test dependency.
- **D5. Display name from Google:** prefilled on **Finish registering** only when it passes the display-name rule, editable, and not stored beyond the pending registration.
- **D6. Mobile number:** required at registration, in international format with the country code, not verified. Not unique.
- **D7. Who sees a mobile number:** the member themselves, and the owner of any group they belong to or have a pending request for. Nobody else.
- **D8. Name:** a single display name, with today's rule.
- **D9. User ID and Name:** stored separately. The Name is shown everywhere a person appears, with `@user-id` beside it to tell people apart. The user ID is the only key used internally and in logs.
- **D10. Editing the profile:** a signed-in member can change their mobile number and display name at any time on a **Profile** screen. The user ID can't be changed. Changes aren't verified and take effect immediately. (Display name was included because it is part of the same profile; drop it here if only the mobile number should be editable.)
