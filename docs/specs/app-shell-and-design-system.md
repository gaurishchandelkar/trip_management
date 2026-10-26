# Spec: App shell and design system

> Status: **ready for planning**. Decisions D1–D4 are recorded at the end. Phase 0 of the product roadmap: make the existing members-and-groups app look and behave like a professional product without changing what it does or how it talks to the backend.

## Expected outcome

The app gets a brand, a consistent visual design (tokens, light and dark themes, reusable components), a responsive layout from phone to desktop, and a URL for every screen, so refresh, the browser's Back button and shared links work.
Members can do exactly what they can today, through the same API calls.

## Constraints

- **No backend change.** Nothing in `backend/` changes, and the API and its error bodies stay as `docs/SPEC.md` describes them.
- **The network contract stays the same.** Every existing inside test in `e2e/test_network_contract.py` keeps its call assertions unchanged: the same calls, in the same order, with the same bodies. That includes `[ME]` on load and `[ME, REGISTER, SIGN_IN, MY_GROUPS, BROWSE]` for sign-in, and each list is fetched once. The helpers in `e2e/app.py` and the selectors in outside tests may follow the new UI, but no assertion is removed or weakened.
- **Same features and rules.** Field validation (`validation.ts`), limits, and every message the UI shows ("Passwords aren't checked yet.", "No group has that name.", "Something went wrong, please try again.", and the rest) stay word for word. Register still does not sign the member in.
- **Accessible names stay**, because tests and assistive technology rely on them: forms **Sign in**, **Register**, **Create group**, **Request to join**; regions **My groups**, **Browse groups**, **Members**, **Pending requests**; the search landmark; buttons **Request to join {group}**, **Approve {name}**, **Reject {name}**, **Sign out**.
- **No third-party origins at run time.** The E2E fixture fails on any request outside the app's origin, so fonts and icons are bundled. No CDN, no Google Fonts.
- **User text is only rendered as text.** No `dangerouslySetInnerHTML`, and icons are React components, never HTML strings.
- Components never call `fetch`. `api.ts` stays the only client.
- TypeScript strict, ESLint strict, no suppressions, coverage gates at 80%.
- New dependencies are limited to `react-router` and `@fontsource-variable/inter` (D1), and `docs/TECH_STACK.md` records each one with its reason. Icons are hand-written SVG components, dialogs use the native `<dialog>` element, and styling is plain CSS with custom properties.

## Acceptance criteria

### Brand and shell

- [ ] Given any screen, then a banner landmark shows the product name **Caravan** (D2) and its logo mark, and the name links to `/`. The signed-out welcome panel shows the tagline "Plan trips together."
- [ ] Given a signed-in member, then the banner shows an avatar with their initials and the accessible text "Signed in as {display name}", plus a **Sign out** button.
- [ ] Given any screen, then the first Tab press focuses a **Skip to content** link that moves focus to the `main` landmark.
- [ ] Given each screen, then `document.title` is "{screen} · Caravan": "Sign in", "Groups", the group's name, or "Page not found".
- [ ] Given the HTML page, then it has a favicon and a `theme-color` meta tag from the brand tokens.

### Routing

- [ ] Given a signed-in member on `/`, when they open a group, then the URL becomes `/groups/{group_id}` and the group's details show.
- [ ] Given a member on `/groups/{group_id}`, when they press the browser's Back button, then they return to `/`, and My groups and Browse groups are reloaded once each (`[MY_GROUPS, BROWSE]`).
- [ ] Given a signed-in member, when they load or refresh `/groups/{group_id}` directly, then the group's details show, and the only API calls are `GET /api/me` then `GET /api/groups/{group_id}`.
- [ ] Given no session, when someone loads `/groups/{group_id}`, then the sign-in screen shows. After they sign in they land on `/groups/{group_id}`, with the calls `[ME, SIGN_IN, GET /api/groups/{group_id}]`.
- [ ] Given a session that ends while on any route (`401`), then the app shows the sign-in screen, and signing in returns to that route.
- [ ] Given an unknown path, or `/groups/{x}` where `x` isn't a positive integer, then a **Page not found** screen with a link to `/` shows, and no API call is made after `GET /api/me`.
- [ ] Given `/groups/{group_id}` for a group that doesn't exist (`404`), then "That group no longer exists." shows with a link back to `/`.
- [ ] Given a production build served by `vite preview`, when any app route is loaded directly, then the app loads (SPA fallback), and `/api/*` is never handled by the fallback.

### Signed-out screen

- [ ] Given no session, then a welcome panel (product name, tagline) shows beside the **Sign in** and **Register** forms on screens 960 px wide or wider, and above them on narrower screens. Both forms are visible without switching tabs.
- [ ] Given each form field, then its label is visible above it, the rule for the field shows as hint text tied to it with `aria-describedby` (for example "3–30 letters, digits, - or _, starting with a letter"), and a failed check marks it `aria-invalid="true"`.

### Signed-in home (`/`)

- [ ] Given a member's groups, then **My groups** shows each one as a card: name, description if any, owner, member count and a status badge (Owner, Member, Pending).
- [ ] Given **Browse groups**, then each group shows the same details. A group with status `none` has a **Request to join {group}** button, and the others show their status badge.
- [ ] Given a member with no groups, then **My groups** shows an empty state, "You aren't in any groups yet.", with a **New group** button that opens the Create group dialog.
- [ ] Given a search with no results, then an empty state shows "No groups found." and a way to clear the search.
- [ ] Given the home screen, then its header has a primary **New group** button and a secondary **Join by name** button (D3). The home screen itself shows only **My groups** and **Browse groups**.
- [ ] Given **New group** or **Join by name** is pressed, then a modal `<dialog>` opens with the **Create group** or **Request to join** form, and focus moves to its first field. The form keeps its accessible name, fields, messages and API calls.
- [ ] Given an open dialog, when the member presses Escape or **Cancel**, then it closes, no request is sent, and focus returns to the button that opened it.
- [ ] Given a dialog's form succeeds, then the dialog closes, focus returns to its opener, and the home screen shows the unchanged message in a `role="status"` callout ("Created {name}." or "Request sent. The owner will decide."). The lists update with the same calls as today (`[CREATE, MY_GROUPS]` or `[POST /api/join-requests]`).
- [ ] Given a dialog's form fails (invalid input, conflict, not found, unavailable), then the dialog stays open with the unchanged alert inside the form, and the entered text is kept.

### Group screen (`/groups/{group_id}`)

- [ ] Given a group, then a header shows its name (level-2 heading), description, owner, member count and the member's status badge, with a **Back to groups** link to `/`.
- [ ] Given a member, then **Members** lists each member with an initials avatar and display name.
- [ ] Given the owner, then **Pending requests** lists each requester with an avatar and the **Approve {name}** and **Reject {name}** buttons, with Approve styled as primary and Reject as danger.

### Components and interaction

- [ ] Given any form or action button, while its request is in flight, then the button is disabled and has `aria-busy="true"`, so a double click sends one request.
- [ ] Given any list while it loads, then skeleton placeholders show, with the accessible text "Loading…".
- [ ] Given any inline feedback, then status messages (`role="status"`) and alerts (`role="alert"`) are styled as success and error callouts with an icon, and the text is unchanged.
- [ ] Given any interactive element focused by keyboard, then a visible focus ring with a contrast of at least 3:1 shows (`:focus-visible`).

### Theme and layout

- [ ] Given `prefers-color-scheme: dark`, then the dark theme applies; otherwise the light theme does.
- [ ] Given a 360 × 740 viewport, then no screen scrolls horizontally, including with a 60-character group name with no spaces, a 50-character display name and a 200-character description.
- [ ] Given `prefers-reduced-motion: reduce`, then transitions and skeleton shimmer are turned off.
- [ ] Given every colour pair used for text in both themes, then the contrast is at least 4.5:1 (3:1 for large text and UI borders), checked by a unit test over the token values.

## Non-functional requirements

- **Accessibility:** WCAG 2.2 AA. One `h1` per screen, landmarks (`banner`, `main`, `search`), touch targets of at least 44 × 44 px on narrow screens, and nothing shown by colour alone (status badges also carry text).
- **Performance:** the production JavaScript is at most 150 KB gzipped, the bundled font files at most 100 KB (Latin subset, `woff2`, `font-display: swap`), and there are no layout shifts when lists load (skeletons reserve their space).
- **Security:** no new origins, no inline HTML from data, and nothing about sessions changes. The route parameter is validated as a positive integer before it reaches `api.ts`.
- **Maintainability:** colours, spacing, radius, shadows, type sizes and motion are defined once as CSS custom properties. Components use the tokens, never raw values.
- **Observability and cost:** no change.

## Failure conditions

- **Backend unreachable on load:** the existing "Something went wrong, please try again." alert, shown inside the shell.
- **Any call fails:** the same messages as today, in the restyled callouts.
- **`401` on any route:** the sign-in screen shows, and the route the member was on is kept for after they sign in. The kept route is a same-origin path only, never a full URL from the query string, so there is no open redirect.
- **Bad route parameter or unknown path:** Page not found, with no API call.
- **Font fails to load:** the system font stack takes over, with no invisible text.
- **Long or unusual text** (any script, maximum lengths, no spaces): it wraps inside its card and never overflows or truncates without a full-text alternative.
- **Request in flight:** repeat submits are blocked by the disabled button, not sent.

## Definition of Done

- [ ] All acceptance criteria are covered by passing tests: vitest for components and tokens, outside E2E journeys for routing, layout and theme, and an inside test for each new journey (direct load, sign-in redirect, not found)
- [ ] Every existing inside test passes with its call assertions unchanged
- [ ] `npm run check` passes
- [ ] `docs/SPEC.md` (Frontend section) and `docs/STATUS.md` are updated, and `docs/TECH_STACK.md` lists any approved new dependency with its reason
- [ ] Screens checked in a real browser with the Playwright MCP server, light and dark, at 360 px and 1280 px, with screenshots attached to the PR
- [ ] `code-reviewer` and `security-reviewer` have run with no unresolved findings

## Out of scope

- Any backend or API change, including renaming groups to crews in the API
- New features: trips, invite links, an inbox or badges, leaving or removing members, editing or deleting groups
- Changing behaviour: auto sign-in after register, a combined sign-in and register screen behind tabs, real passwords, undo or confirm dialogs
- Toast notifications that replace inline form feedback
- A manual theme toggle (the theme follows the system)
- Internationalisation, PWA and offline use, and analytics

## Decisions

Confirmed by the human on 2026-10-26.

- **D1. Dependencies:** `react-router` for URLs and `@fontsource-variable/inter` for a self-hosted Inter font are approved. There's no icon library (a handful of hand-written SVG components), no UI kit (native `<dialog>`), no data-fetching library (the pinned network contract stays easy to keep), and no CSS framework (plain CSS custom properties).
- **D2. Product name:** **Caravan**, tagline "Plan trips together." Only the UI and the HTML title change. The repo, package names, docs headings and API keep their names, and the UI keeps saying "groups" until the crews rename (Phase 2).
- **D3. Home layout:** **Create group** and **Request to join** move into native modal dialogs, opened by **New group** (primary) and **Join by name** (secondary) in the home header. The E2E helpers gain the click that opens each dialog.
- **D4. Visual direction:** sunset coral primary (`#E8552F` family) on slate neutrals, in light and dark themes. Plain `#E8552F` is below 4.5:1 against white, so text-bearing uses (button labels, links) use a darker coral shade from the same family. The contrast test decides the exact values.
