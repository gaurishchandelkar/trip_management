# Product Spec

Trip Management for friends. Members register, sign in, and organise themselves into groups: anyone can create a group, and others join once the owner approves.
(Spec: `docs/specs/members-and-groups.md`.)

> **Local and trusted use only.** Sign-in asks for a password but doesn't check it yet: anyone who knows a user ID can sign in as that member. Real passwords come in a later spec. Don't expose the app beyond your own machine or network.

## Members and sessions

- A member registers with a **user ID** (3–30 letters, digits, `-` or `_`, starting with a letter) and a **display name** (1–50 letters from any script, with single spaces, hyphens or apostrophes between them).
- User IDs are case-insensitive: they're stored and shown in lower case, so `ADA` and `ada` are the same member.
- Signing in needs a registered user ID and a non-empty password of up to 128 characters. The password is never stored, logged or returned.
- A session is a random token in a `session` cookie (`HttpOnly`, `SameSite=Strict`, `Path=/api`). Only its SHA-256 hash is stored. It lasts **7 days** from sign-in, and signing out ends it.

## Groups and joining

- Any member can create a group and becomes its owner and first member. Group names are 1–60 letters, digits, spaces and `- ' & . ,`, starting with a letter or digit, with single spaces. They're unique, ignoring case. A description of up to 200 characters is optional.
- Members browse groups, optionally searching by part of the name (ignoring case). Browsing returns at most 50 groups, sorted by name.
- A member asks to join from the browse list or by typing a group's exact name (ignoring case). Either way the request waits for the owner.
- Only the owner sees pending requests, and only the owner can approve or reject them. Approved requesters become members; rejected ones can ask again.
- Members see a group's member list, by display name only. Non-members see only its name, description, owner and member count.
- **Limits:** a group has at most 50 members, a member owns at most 20 groups, and a member has at most 20 pending requests.

## Backend API

Bodies are JSON and unknown fields are refused. Text fields refuse invisible format characters (such as zero-width joiners and direction overrides) and control characters. Every route except the first three needs a session cookie.

| Method | Path | Success |
|---|---|---|
| GET | `/api/health` | `200 {"status": "ok"}` |
| POST | `/api/members` `{user_id, display_name}` | `201 {user_id, display_name}` |
| POST | `/api/sign-in` `{user_id, password}` | `200 {user_id, display_name}` and the session cookie |
| POST | `/api/sign-out` | `204`, cookie cleared |
| GET | `/api/me` | `200 {user_id, display_name}` |
| GET | `/api/me/groups` | `200 [group]`, the groups I own or belong to |
| POST | `/api/groups` `{name, description?}` | `201 group` |
| GET | `/api/groups?q=` | `200 [group]`, at most 50, sorted by name |
| GET | `/api/groups/{group_id}` | `200 group` plus `members` as `[{display_name}]` (members only) and `pending_requests` (owner only), otherwise `null` |
| POST | `/api/groups/{group_id}/join-requests` | `201 {request_id, group_id, status}` |
| POST | `/api/join-requests` `{group_name}` | `201 {request_id, group_id, status}` |
| POST | `/api/join-requests/{request_id}/approve` | `200 {request_id, group_id, status}` |
| POST | `/api/join-requests/{request_id}/reject` | `200 {request_id, group_id, status}` |

A `group` is `{group_id, name, description, owner_display_name, member_count, my_status}`, where `my_status` is `owner`, `member`, `pending` or `none`.

### Errors

Error bodies are fixed strings and never echo the input.

| Status | Body `detail` | When |
|---|---|---|
| 401 | `Invalid user ID or password` | Sign-in with an unregistered user ID |
| 401 | `Not signed in` | No session, or an unknown, ended or expired one |
| 403 | `Forbidden` | A non-owner approves or rejects |
| 404 | `Not found` | Unknown group, unknown group name, or a request that doesn't exist or was already decided |
| 409 | `User ID already taken`, `Group name already taken`, `Request already pending`, `Already a member`, `Limit reached` | Conflicts and limits |
| 413 | `Request too large` | A request body over 4 KB |
| 422 | `Invalid request` | Any invalid input |
| 503 | `Service unavailable` | The database can't be used |

## Frontend

- On load it checks the session (`GET /api/me`) and shows "Loading…" until it knows.
- Signed out: a **Sign in** form (User ID, Password, with the note "Passwords aren't checked yet.") and a **Register** form (User ID, Display name).
- Signed in: the display name, a **Sign out** button, **My groups**, a **Create group** form, a **Request to join** form (by group name), and **Browse groups** with a search box and a **Request to join** button per group.
- Opening a group shows its details; members see the member list, and the owner also sees pending requests with **Approve** and **Reject** buttons.
- Forms check input before sending and show their own messages. User-supplied text is only ever rendered as text.
- A `401` returns the app to the sign-in screen. Other failures show "Something went wrong, please try again."

## Storage

SQLite through SQLAlchemy 2.x, in the file named by `TRIP_DB_PATH` (default `trip.db` in the repo root, git-ignored). The schema is created on startup; there are no migrations yet.

## Not in scope

Trips (itineraries, expenses), real passwords, invitations, leaving or removing members, editing or deleting groups, notifications, deployment.
