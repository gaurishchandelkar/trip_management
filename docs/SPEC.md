# Product Spec

Trip Management for friends. Members sign in with Google, and organise themselves into groups: anyone can create a group, and others join once the owner approves.
(Specs: `docs/specs/members-and-groups.md`, `docs/specs/sso-registration.md`.)

> **Local use for now.** Sign-in is through Google, but the app runs over plain HTTP with no deployment set up, and its cookies aren't `Secure`. Don't expose it beyond your own machine or network.

## Members and sessions

- People sign in only with **Google** (OpenID Connect: authorization code with PKCE, `state` and `nonce`, the ID token checked against Google's keys). Google is on when `TRIP_GOOGLE_CLIENT_ID` and `TRIP_GOOGLE_CLIENT_SECRET` are set; otherwise the sign-in screen says "Sign-in isn't set up yet. See the README." and the auth routes answer `404`.
- The first time a Google account signs in, the person **finishes registering**: a **user ID** (3–30 letters, digits, `-` or `_`, starting with a letter), a **display name** (1–50 letters from any script, with single spaces, hyphens or apostrophes between them; prefilled from Google's name only when that passes the rule) and a **mobile number**.
- A **mobile number** is international: `+`, a country code that doesn't start with `0`, 8 to 15 digits in all. Spaces and hyphens are allowed when typing (at most 20 characters) and removed before storing. It isn't verified, and two members may share one.
- User IDs are case-insensitive: they're stored and shown in lower case, so `ADA` and `ada` are the same member. The user ID never changes, and it's the only key used internally and in logs. The display name and mobile are stored in their own columns and only shown.
- One Google account is one member, matched by Google's subject (`sub`) only, never by email. Only the provider name and subject are stored for the link: no email, Google name, picture or tokens.
- A sign-in waiting for Google, and a registration waiting for its user ID, each last **10 minutes**, are single-use, and are capped at 1,000 open at once.
- A session is a random token in a `session` cookie (`HttpOnly`, `SameSite=Strict`, `Path=/api`). Only its SHA-256 hash is stored. It lasts **7 days** from sign-in, and signing out ends it (but not the Google session).
- A member edits their **profile** (display name and mobile, saved together) at any time. Changes take effect at once.

## Groups and joining

- Any member can create a group and becomes its owner and first member. Group names are 1–60 letters, digits, spaces and `- ' & . ,`, starting with a letter or digit, with single spaces. They're unique, ignoring case. A description of up to 200 characters is optional.
- Members browse groups, optionally searching by part of the name (ignoring case). Browsing returns at most 50 groups, sorted by name.
- A member asks to join from the browse list or by typing a group's exact name (ignoring case). Either way the request waits for the owner.
- Only the owner sees pending requests, and only the owner can approve or reject them. Approved requesters become members; rejected ones can ask again.
- Members see a group's member list, by display name and user ID. Non-members see only its name, description, owner and member count.
- **Mobile numbers** are seen only by the member themselves (on their profile) and by the owner of a group they belong to or have asked to join. Nobody else gets them, in any response.
- **Limits:** a group has at most 50 members, a member owns at most 20 groups, and a member has at most 20 pending requests.

## Backend API

Bodies are JSON and unknown fields are refused. Text fields refuse invisible format characters (such as zero-width joiners and direction overrides) and control characters. Routes marked *session* need a session cookie.

| Method | Path | Success |
|---|---|---|
| GET | `/api/health` | `200 {"status": "ok"}` |
| GET | `/api/auth/providers` | `200 {"providers": ["google"]}`, or `[]` when Google isn't set up |
| GET | `/api/auth/google/start?return_to=` | `302` to Google, with a flow cookie (`HttpOnly`, `SameSite=Lax`, `Path=/api/auth`, 10 minutes). `return_to` must be a path in the app, otherwise `/` |
| GET | `/api/auth/google/callback?code=&state=` | `302` to `return_to` with the session cookie; to `/register/complete` with a pending-registration cookie (`Strict`, 10 minutes); or to `/?sign_in=failed` or `/?sign_in=cancelled` |
| GET | `/api/auth/registration` | `200 {display_name, return_to}` for the pending registration |
| POST | `/api/auth/registration` `{user_id, display_name, mobile}` | `201 {user_id, display_name, mobile}` and the session cookie |
| POST | `/api/sign-out` *session* | `204`, cookie cleared |
| GET | `/api/me` *session* | `200 {user_id, display_name, mobile}` |
| POST | `/api/me/profile` *session* `{display_name, mobile}` | `200 {user_id, display_name, mobile}` |
| GET | `/api/me/groups` *session* | `200 [group]`, the groups I own or belong to |
| POST | `/api/groups` *session* `{name, description?}` | `201 group` |
| GET | `/api/groups?q=` *session* | `200 [group]`, at most 50, sorted by name |
| GET | `/api/groups/{group_id}` *session* | `200 group` plus `members` (members only) and `pending_requests` (owner only), otherwise `null` |
| POST | `/api/groups/{group_id}/join-requests` *session* | `201 {request_id, group_id, status}` |
| POST | `/api/join-requests` *session* `{group_name}` | `201 {request_id, group_id, status}` |
| POST | `/api/join-requests/{request_id}/approve` *session* | `200 {request_id, group_id, status}` |
| POST | `/api/join-requests/{request_id}/reject` *session* | `200 {request_id, group_id, status}` |

A `group` is `{group_id, name, description, owner_user_id, owner_display_name, member_count, my_status}`, where `my_status` is `owner`, `member`, `pending` or `none`. `members` items are `{user_id, display_name}` and `pending_requests` items are `{request_id, user_id, display_name}`; for the owner only, each also has `mobile`. For anyone else the `mobile` key is absent.

The callback never answers with JSON: a missing, reused, expired or mismatched `state`, a missing flow cookie, a `code` or `state` over 512 characters, a token that fails a check, Google being down or slow (5 seconds), a full table, or a storage failure all redirect to `/?sign_in=failed`.

### Errors

Error bodies are fixed strings and never echo the input.

| Status | Body `detail` | When |
|---|---|---|
| 401 | `Not signed in` | No session, or an unknown, ended or expired one; no usable pending registration |
| 403 | `Forbidden` | A non-owner approves or rejects |
| 404 | `Not found` | Unknown group, unknown group name, a request that doesn't exist or was already decided, or an auth route while Google isn't set up |
| 409 | `User ID already taken`, `Account already linked`, `Group name already taken`, `Request already pending`, `Already a member`, `Limit reached` | Conflicts and limits |
| 413 | `Request too large` | A request body over 4 KB |
| 422 | `Invalid request` | Any invalid input, including a `user_id` sent to `/api/me/profile` |
| 503 | `Service unavailable` | The database can't be used |

## Frontend

The app is branded **Caravan** ("Plan trips together."). Its design spec is `docs/specs/app-shell-and-design-system.md`.

- **Shell:** every screen has a banner with the Caravan logo and name, which links home and is the page's only `h1`. Signed in, the banner also shows an initials avatar, "Signed in as {display name}" with "@{user ID}" beneath, a **Profile** link and **Sign out**. The first Tab reaches **Skip to content**. The browser tab reads "{screen} · Caravan".
- **Addresses:** `/` is home, `/groups/{group_id}` is a group, `/profile` is the member's profile, `/register/complete` finishes a Google registration, and anything else is **Page not found**. A group ID that isn't a positive whole number is not found, with no API call. Refresh, Back and shared links work.
- On load the app checks the session (`GET /api/me`) and shows loading placeholders until it knows.
- **Signed out:** at any address, a welcome panel beside (960 px and wider) or above the **Sign in** panel, with **Continue with Google** (or "Sign-in isn't set up yet."). Signing in returns to the address the person was on. A `?sign_in=` result shows "Couldn't sign in with Google. Please try again.", "Sign-in was cancelled." or "Your sign-in expired. Please start again.", and is removed from the address.
- **Finish registering** (`/register/complete`): User ID, Display name and Mobile number, each with its rule shown up front, and the note "Group owners can see your mobile number." On success the member is signed in and lands where they started.
- **Home:** the title "Groups" with **New group** and **Join by name** buttons, **My groups** and **Browse groups** as cards ("by {owner} (@{user ID})") with status badges, and a search box. **New group** and **Join by name** open modal dialogs with the **Create group** and **Request to join** forms. On success the dialog closes and Home shows the result. On failure it stays open with the typed text. Empty lists say so, with one action: **New group**, or **Clear search** after a search found nothing.
- **Group:** a **Back to groups** link, then the group's details, its owner and the member's status. Members see the member list, each with "@{user ID}" beside the name. The owner also sees pending requests with **Approve** and **Reject** (labelled "Approve {name} (@{user ID})"), and every member's and requester's mobile as a phone link.
- **Profile** (`/profile`): a **Back to groups** link, the user ID as read-only text, and Display name and Mobile number fields filled with the current values. **Save** shows "Profile saved." and updates the banner.
- Forms show each field's rule up front, check input before sending, mark a failed field invalid and show their own messages. A button is disabled while its request is in flight, so a double click sends one request. User-supplied text is only ever rendered as text.
- A `401` returns the app to the sign-in screen at the same address. An explicit sign-out returns home. Other failures show "Something went wrong, please try again."
- **Appearance:** light and dark themes follow the system setting, motion stops under reduced motion, and the Inter font is bundled with a system fallback. Every text colour pair meets WCAG AA contrast (`frontend/src/theme/tokens.test.ts`). No screen scrolls sideways at 360 px, and buttons and links are at least 44 px tall on phones. The Google mark is drawn from the app's own source; nothing loads from Google.
- **Screenshots for review:** every CI run captures sign-in, home, the New group dialog, a group, the profile and Page not found, in light and dark at 360 and 1280 px, with fixed sample data: 24 images, published as the `ui-screenshots` artifact (`docs/specs/ci-screenshot-artifacts.md`).

## Storage

SQLite through SQLAlchemy 2.x, in the file named by `TRIP_DB_PATH` (default `trip.db` in the repo root, git-ignored). The schema is created on startup; there are no migrations yet. A database from before Google sign-in (a `members` table without `mobile`) stops startup with a message to delete it, and is left untouched.

## Not in scope

Trips (itineraries, expenses), providers other than Google, verifying mobile numbers, changing a user ID, linking or unlinking Google accounts, invitations, leaving or removing members, editing or deleting groups, notifications, deployment, a manual theme switch.
