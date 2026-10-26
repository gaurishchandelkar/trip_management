# Plan: App shell and design system

Spec: `docs/specs/app-shell-and-design-system.md`
Status: **Done** <!-- Awaiting approval | Approved | In progress | Done -->
Approved: 2026-10-26 by the repo owner, in conversation.

## Approach

This is a frontend-only change. `backend/` and `api.ts` don't change, and every existing inside test keeps its call assertions.
The design system is plain CSS:
- `frontend/src/theme/tokens.css` is the only file with raw colour, spacing, radius, shadow, type and motion values, with a light `:root` block and a `prefers-color-scheme: dark` block.
- `theme/base.css` holds element defaults, the focus ring, reduced motion and the skip link.
- Each component's CSS uses `var(--…)` only.

Reusable components live in `frontend/src/ui/`: Button, Field, Card, Badge, Avatar, Callout, Skeleton, EmptyState, Dialog and Icon. The screens keep their current files (`App`, `SignedOut`, `Groups`, `GroupView`) and are rebuilt on these components.

Routing uses `react-router` in declarative mode. `main.tsx` mounts `<BrowserRouter>`, and `App` keeps its session union and renders `<Routes>` for `/`, `/groups/:groupId` and `*` only when signed in.
While signed out, the sign-in screen renders at whatever the current URL is, and the URL is left alone. After sign-in, the route that was asked for simply renders. That gives "return to where you were" with no redirect parameter, so there's no open-redirect surface at all.

**Main trade-off:** going back to Home remounts it, which reloads both lists. That's what the spec asks for, and it removes the `visit`/`version` counters. The cost is that the search term isn't kept across navigation. Keeping it would need shared state the spec doesn't ask for.

## Human attention needed

- **New dependencies (approved in spec D1):**
  - `react-router`: the current 7.x release, which supports React 19, used in declarative mode only.
  - `@fontsource-variable/inter`: imported once in `main.tsx`.

  Both go in `dependencies`, `package-lock.json` changes, and `npm audit` must stay clean. Vite bundles the font's `woff2` files from the package, so no request leaves the app's origin.
- **E2E helper and selector changes** (allowed by the spec: no assertion removed or weakened):
  - Groups in the lists become **links** (`role="link"`) instead of buttons, because opening one is navigation. `open_group` changes from `get_by_role("button", name=…)` to `get_by_role("link", name=…)`.
  - `create_group` gains a click on **New group**, and its success check reads the page-level status instead of the form's.
  - The request-by-name steps gain a click on **Join by name**.
  - "Back to groups" becomes a link.

  The vitest suites (`App.test.tsx`, `Groups.test.tsx`) render inside a `MemoryRouter`.
- **Heading levels:** the spec and E2E expect the group name as a level-2 heading. So the brand stays the page's only `h1`, in the banner, as "Trip Management" is today, and screen and section titles are `h2`/`h3`.
- **Explicit sign-out goes to `/`.** It's not stated in the spec. If you sign out on `/groups/5`, the next person to sign in on that browser starts at Home, not on your last group. A `401` keeps the route, as the spec says. Sign-out still sends only `[SIGN_OUT]`.
- **jsdom and `<dialog>`:** jsdom may not implement `showModal()`/`close()`. If it doesn't, `test-setup.ts` gets a minimal test-only stub that toggles the `open` attribute. The E2E tests in real Chromium cover modal behaviour, focus return and Escape. This changes no thresholds and adds no suppressions.
- **New checks (each gets a negative proof):**
  - A token contrast test that parses `tokens.css` and checks named text, surface, border and focus pairs in both themes.
  - A raw-colour scan that fails on any hex, `rgb()` or `hsl()` value in `frontend/src/**/*.css` outside `tokens.css`.
- **Holding a request in E2E:** to see a skeleton under reduced motion, one E2E test holds `GET /api/me/groups` in a `page.route` handler and releases it after asserting, instead of sleeping. That fits the no-sleeps rule, but it's a new pattern in `e2e/`.
- **Bundle and font budgets** (150 KB JS gzipped, 100 KB font) are checked once from `vite build` output and Playwright network sizes in Phase 4, not by a permanent gate. Say if you want a permanent check in `npm run check`. That would be a harness change.
- No changes to `backend/`, `.claude/`, `.github/`, `lefthook.yml`, CI or security config.

## Phase 1: Design tokens, components and in-place restyle

- `theme/tokens.css`:
  - Sunset coral primary with a darker text-safe coral, slate neutrals, and success, warning and danger colours, for light and dark.
  - Spacing on a 4 px scale, radius, shadows, and the type scale 12/14/16/20/24/32 with Inter and a system fallback stack.
  - Focus ring and motion durations.
- `theme/base.css`: element defaults, `overflow-wrap: anywhere` on text, `:focus-visible` ring, and `@media (prefers-reduced-motion: reduce)` turning off transitions and animation.
- `main.tsx`: imports the font and the theme. `styles.css` is replaced by the theme and component CSS.
- `ui/` components:
  - `Button` (primary, secondary, ghost, danger; `busy` sets `disabled` and `aria-busy`).
  - `Field` (visible label, hint linked with `aria-describedby`, `invalid` → `aria-invalid`).
  - `Card`, `Badge` (Owner, Member, Pending, text always shown), `Avatar` (initials from the first code point of up to two words, `aria-hidden`, name always shown beside it).
  - `Callout` (the restyled `FeedbackMessage`, same roles and text, with an icon), `Skeleton` (reserves its space, accessible "Loading…"), and `Icon` (inline SVG components).
- Restyle `SignedOut`, `Groups` and `GroupView` in place: same layout order, same accessible names, same messages.
  - Group lists become cards with badges. Members and pending requests get avatars. Approve is primary and Reject is danger.
  - Each field gets its rule as hint text: `USER_ID_HINT`, `DISPLAY_NAME_HINT` and `GROUP_NAME_HINT`, plus new short hints where none exist, such as "Up to 200 characters" for the description.
  - Every submit and action button is busy while its request is in flight.

Notes from implementation:
- Badges keep the existing status text ("You own this group", "You're a member", "Request pending") rather than the shorter "Owner, Member, Pending" in the spec, because the spec's constraints keep every UI message word for word and existing tests assert them.
- Vitest replaces imported CSS (even `?raw`) with an empty string, so the token tests read the stylesheets from disk with `node:fs` in the node environment, and assert each file has content so the scan can't pass empty.
- `Card` is a CSS class (`.card`), not a component: it had no behaviour to own.
- Browser check found the focus ring hard to see on primary buttons of the same colour, so buttons use an offset outline.

Success criteria:
- [x] Vitest `theme/tokens.test.ts`: every named text/surface pair is at least 4.5:1 and every border and focus-ring pair is at least 3:1, in both the light and dark blocks (44 pair tests)
- [x] Negative proof: temporarily set the light `--color-text-muted` to `#bbbbbb`. The contrast test fails while the other unit tests pass. Revert (2 failed, 163 passed; reverted)
- [x] Vitest raw-colour scan: no hex, `rgb()` or `hsl()` value in any `frontend/src/**/*.css` except `theme/tokens.css`
- [x] Negative proof: temporarily add `color: #ff0000` to a component stylesheet. The scan fails. Revert (`ui/ui.css uses tokens, never raw colours` failed, 164 passed; reverted)
- [x] Vitest `ui/*.test.tsx`:
  - a busy `Button` is disabled with `aria-busy="true"`
  - `Field` ties its hint with `aria-describedby` and sets `aria-invalid` only when invalid
  - `Avatar` gives "AL" for "Ada Lovelace" and one letter for a single word, and works for non-Latin names
  - `Badge` renders its text
  - `Skeleton` exposes "Loading…"
  - `Callout` keeps `role="status"` and `role="alert"` with unchanged text
- [x] Vitest (`Groups.test.tsx` "while a request is in flight", `App.test.tsx` "marking invalid fields"):
  - a double click on **Create group**, **Send request**, **Request to join {group}** and **Approve {name}** sends exactly one request
  - a failed sign-in or register check marks the failing field `aria-invalid="true"`
- [x] All existing vitest tests pass with unchanged assertions, and coverage stays at least 80% (100% lines, 96.75% branches)
- [x] All existing E2E outside and inside tests pass with **no** changes to `e2e/` (names, roles and messages are untouched in this phase). New tests were only appended (32 passed)
- [x] New E2E outside test `test_theme_follows_the_system_colour_scheme[light|dark]`, paired with `test_dark_theme_needs_no_api_calls`
- [x] Playwright MCP: sign-in, home and group screens checked in light and dark at 1280 px. Focus rings are visible when tabbing
- [x] `npm run check` passes (build, lint, unit, integration here; functional ran separately: 32 passed)

## Phase 2: Routing and app shell

- `npm install react-router`. `main.tsx` mounts `<BrowserRouter>`.
- `App`: the session union stays. When signed in it renders `<Routes>`:
  - `/` → Home (`Groups`)
  - `/groups/:groupId` → `GroupRoute`, which accepts only `^[1-9][0-9]*$` and a safe integer, otherwise NotFound, before `GroupView` calls `api.ts`
  - `*` → `NotFound` (a "Page not found" heading and a link to `/`)
- `Groups`: group names become `<Link>`s to `/groups/{id}`, and the `openGroupId` and `visit` state are removed. `GroupView`: "Back to groups" becomes a `<Link to="/">`, it reads the ID from the route, and it shows the member's status badge.
  - A missing group shows "That group no longer exists." with a link to `/`.
- `ui/AppHeader`: a banner landmark with the logo mark and the `h1` "Caravan" linking to `/`. When signed in, it also has an avatar, a visually hidden "Signed in as {name}" and the **Sign out** button. Sign-out navigates to `/`.
- `ui/SkipLink`: "Skip to content", the first focusable element, targeting `<main id="main" tabIndex={-1}>`.
- `useDocumentTitle(screen)`: "Sign in · Caravan", "Groups · Caravan", "{group name} · Caravan", "Page not found · Caravan".
- `frontend/index.html`: title "Caravan", `<link rel="icon" href="/favicon.svg">`, and `<meta name="theme-color">` in the brand coral. Add `frontend/public/favicon.svg`.
- E2E helpers: `open_group` uses `role="link"`. Add `load_path(page, path)`, which waits for `GET /api/me` like `load`.

Notes from implementation:
- `react-router` installed at **8.5.0**, not 7.x: 8.x is the current release. Its declarative API (`BrowserRouter`, `Routes`, `Route`, `Link`, `useParams`, `useNavigate`, `MemoryRouter`) is unchanged, its peers are React 19.2+, and it needs Node 22.22+, which `.nvmrc` (24) meets.
- `load(page, path="/")` gained an optional path instead of adding a separate `load_path`.
- The signed-in routes live in `AppRoutes.tsx`, so `App` and the vitest suites share one route table.
- A missing group sets the title "Group not found · Caravan", a fifth title the spec's list didn't name.
- `/groups/07` (a leading zero) is also not found, since `^[1-9][0-9]*$` is the rule.
- The shell journey (`test_shell_shows_the_brand_title_and_icon`) makes exactly the sign-in calls, so it's added to the `@covers` of the existing `test_sign_in_loads_my_groups_and_the_browse_list_once` rather than duplicating that inside test.

Success criteria:
- [x] Vitest: `GroupRoute` renders NotFound with no `getGroup` call for `/groups/abc`, `/groups/0`, `/groups/-1`, `/groups/07` and `/groups/99999999999999999999` (`routes` suite)
- [x] Vitest: an unknown path renders "Page not found" with a link to `/`. Each screen sets the expected `document.title` (Sign in, Groups, group name, Page not found, Group not found)
- [x] Vitest: a `401` on `/groups/7` shows sign-in at the same path, and signing in renders the group again (`keeps the address when the session ends...`)
- [x] Vitest (updated): "goes back to the home view and reloads its lists" now follows the Back link and asserts one call to each list
- [x] E2E outside: `test_opening_a_group_gives_it_an_address_and_back_returns_home`
- [x] E2E inside: `test_back_reloads_each_home_list_once` asserts exactly `[MY_GROUPS, BROWSE]`
- [x] E2E outside: `test_a_group_address_opens_directly_and_survives_a_refresh`
- [x] E2E inside: `test_group_address_checks_the_session_then_loads_only_that_group` asserts exactly `[ME, GET /api/groups/{id}]`
- [x] E2E outside: `test_signed_out_visitor_lands_on_the_group_after_signing_in`
- [x] E2E inside: `test_signing_in_on_a_group_address_loads_only_that_group` asserts exactly `[ME, SIGN_IN, GET /api/groups/{id}]` (401, 200, 200)
- [x] E2E outside: `test_unknown_address_shows_page_not_found[/nowhere|/groups/abc]`
- [x] E2E inside: `test_unknown_address_makes_no_call_after_the_session_check` asserts only `[ME]`
- [x] E2E outside: `test_missing_group_says_so`, paired with `test_missing_group_asks_once_and_gets_a_generic_404`
- [x] E2E outside: `test_skip_link_moves_focus_to_the_main_content`, paired with `test_skip_link_makes_no_calls`
- [x] E2E outside: `test_shell_shows_the_brand_title_and_icon`
- [x] E2E (existing, updated selectors only): every existing journey passes, including `test_shows_alert_when_backend_fails` and "Signed in as Ada Lovelace" (47 passed)
- [x] `vite preview` SPA fallback: direct loads of `/groups/{id}` serve the app, and `GET /api/groups/{id}` reaches the backend (asserted in the inside tests)
- [x] Every new outside journey has a paired inside test. `node --test scripts/harness-config.test.mjs` passes (8/8)
- [x] `npm run check` passes (build, lint, unit, integration; functional: 47 passed)

## Phase 3: Home layout, dialogs and signed-out layout

- `ui/Dialog`: a native `<dialog>` opened with `showModal()`, labelled by its form heading, with a **Cancel** button. Escape and Cancel close it without sending anything, and focus returns to the opener.
- Home header: the screen title "Groups", a primary **New group** button and a secondary **Join by name** button. The Create group and Request to join forms move into dialogs, keeping their names, fields, messages and calls.
  - On success the dialog closes, and Home shows the unchanged message in a page-level `role="status"` callout.
  - On failure the dialog stays open with the alert and the entered text.
- Empty states (`ui/EmptyState`):
  - My groups: "You aren't in any groups yet." with a **New group** button that opens the dialog.
  - Browse with no results: "No groups found." with a **Clear search** button, which empties the box and reloads the unfiltered list.
- Signed-out screen: a welcome panel ("Caravan", "Plan trips together.") beside the two forms at 960 px and wider, and above them on narrower screens. Both forms stay visible.
- E2E helpers: `create_group` clicks **New group** first and reads the page-level status. The request-by-name steps click **Join by name** first.

Notes from implementation:
- jsdom has `HTMLDialogElement` but no `showModal()` or `close()`, so `test-setup.ts` stubs those two, guarded for the node-environment token test.
- `Dialog` moves focus to the first field itself after `showModal()`, so jsdom and browsers behave the same. Its content mounts only while open, so each opening starts with an empty form.
- With the "Groups" screen title as the `h2`, the My groups and Browse groups section headings are now `h3`. No test depended on their level.
- **Clear search** appears only when the empty result came from a search term. With no term, there's nothing to clear.
- The E2E clear-search journey checks that the list is no longer empty rather than for a specific group, because browse returns at most 50 groups by name and the shared E2E database grows during a run.

Success criteria:
- [x] Vitest (`creating a group`): **New group** opens a dialog with the name field focused; Cancel sends nothing; success closes it and shows "Created Goa 2027."; a `409` keeps it open with the typed name
- [x] Vitest (`asking to join`): **Join by name** success closes the dialog, shows "Request sent. The owner will decide." and marks the listed group pending; "No group has that name." keeps it open with the typed name
- [x] Vitest: the empty My groups state's **New group** opens the dialog. **Clear search** empties the box and calls `browseGroups(undefined)`, and isn't offered when nothing was searched
- [x] E2E outside: `test_escape_closes_the_new_group_dialog_and_returns_focus`
- [x] E2E inside: `test_closing_a_dialog_sends_nothing` (Escape and Cancel, both dialogs: no calls)
- [x] E2E (existing, updated helpers): the create, request-by-name, unknown-name and duplicate-name journeys pass with unchanged messages
- [x] E2E inside (existing): their calls are still `[CREATE, MY_GROUPS]` and `[POST /api/join-requests]`, assertions unchanged
- [x] E2E outside: `test_clear_search_shows_every_group_again`
- [x] E2E inside: `test_clear_search_sends_one_unfiltered_browse` asserts exactly `[BROWSE]` with no `q`
- [x] E2E outside: `test_welcome_panel_sits_beside_the_forms_wide_and_above_them_narrow`, paired with `test_resizing_the_signed_out_screen_makes_no_calls`
- [x] `npm run check` passes (build, lint, unit, integration; functional: 53 passed)

## Phase 4: Responsive polish, budgets and docs

- Fix whatever the layout tests and browser checks turn up:
  - narrow-screen spacing
  - 44 px touch targets below 640 px
  - wrapping of long names and descriptions
- Update the docs:
  - `docs/SPEC.md` Frontend section: the brand, routes, dialogs, themes, and that both forms are visible
  - `docs/STATUS.md`
  - `docs/TECH_STACK.md`: the two dependencies and why there's no UI kit or data library

Notes from implementation:
- The touch-target test failed first (8 targets under 44 px, such as the skip link at 40 px and group-name links at 25 px). It passed after a `max-width: 639px` rule gave buttons, fields and navigation links a 44 px minimum height. The sideways-scroll test passed with no change: `overflow-wrap: anywhere` from Phase 1 already wraps long names.
- The four phone, motion and font journeys are paired with two inside tests: a phone screen makes the same sign-in and create calls, and the motion and font preferences make no calls.
- Keyboard check of the native dialog: Shift+Tab from the first field leaves the page for the browser's own UI, and the next Tab returns to that field. Nothing behind the modal is reachable, which is native `<dialog>` behaviour.

Success criteria:
- [x] E2E outside: `test_no_screen_scrolls_sideways_on_a_phone` checks the signed-out screen, Home with a 60-character group name with no spaces and a 200-character description, that group with a 50-character display name, and Page not found
- [x] E2E outside: `test_buttons_and_links_are_easy_to_tap_on_a_phone` (Home and group screen, every visible button and link at least 44 px)
- [x] E2E outside: `test_reduced_motion_stops_animation` (held `GET /api/me/groups`, skeleton `animation-name: none`, button `transition-duration: 0s`)
- [x] E2E outside: `test_text_shows_in_a_system_font_when_the_web_font_fails`
- [x] `vite build` output: JS is **87.02 KB** gzipped (276.81 KB raw), against a 150 KB budget. CSS is 3.71 KB gzipped
- [x] Playwright MCP: an English screen fetches only `inter-latin-wght-normal.woff2`, which is **48.25 KB** in the build, against a 100 KB budget
- [x] Playwright MCP: every screen checked in light and dark, at 360 px and 1280 px (screenshots in `.playwright-mcp/`, git-ignored, for the PR). The New group dialog was opened, used and closed by keyboard only, with focus returning to **New group**
- [x] `docs/SPEC.md`, `docs/STATUS.md` and `docs/TECH_STACK.md` are updated
- [x] `npm run check` passes

## Final verification

- [x] `npm run check` passes: build, lint, unit (188 vitest, 61 pytest), integration (102), functional (59 E2E), security and architecture
- [x] Every acceptance criterion in the spec is covered by a test (mapping below)
- [x] Every existing inside test passes with its call assertions unchanged. `git diff main -- e2e/test_network_contract.py` removes only one `@covers` line (extended with a name) and five selectors (link instead of button, dialog opened first, page-level status)

### Spec coverage

| Spec acceptance criterion | Phase and check |
|---|---|
| Banner, Caravan, logo, link to `/`; tagline | 2 banner E2E; 3 welcome panel E2E |
| Avatar, "Signed in as", Sign out | 2 existing journey plus banner E2E |
| Skip to content | 2 skip-link E2E |
| `document.title` per screen | 2 vitest plus E2E |
| Favicon, `theme-color` | 2 E2E |
| Open group changes the URL; Back reloads lists | 2 outside plus inside E2E |
| Direct load and refresh | 2 outside plus inside E2E |
| Signed-out deep link, then sign in to the same route | 2 outside plus inside E2E |
| `401` keeps the route | 2 vitest |
| Unknown path, bad ID: Page not found, no call | 2 vitest plus outside and inside E2E |
| Missing group | 2 E2E |
| SPA fallback, `/api` untouched | 2 direct-load E2E |
| Welcome panel layout | 3 E2E at 1280 and 360 |
| Hints, `aria-describedby`, `aria-invalid` | 1 vitest |
| My groups cards, Browse badges and buttons | 1 existing journeys plus vitest |
| Empty My groups with **New group** | 3 vitest |
| No results, Clear search | 3 vitest plus outside and inside E2E |
| Header buttons, home shows only the lists | 3 vitest |
| Dialog opens and focuses the first field | 3 vitest |
| Escape or Cancel closes it, no request, focus returns | 3 vitest plus E2E |
| Dialog success: closes, status, same calls | 3 vitest plus existing inside E2E |
| Dialog failure stays open with text kept | 3 vitest plus existing duplicate-name and unknown-name E2E |
| Group header, badge, Back link | 1 badge vitest; 2 Back link E2E |
| Members with avatars | 1 vitest |
| Pending requests with avatars and button styles | 1 vitest plus existing approve and reject E2E |
| Busy buttons, one request on double click | 1 vitest |
| Skeletons with "Loading…" | 1 vitest; 4 E2E |
| Callouts keep roles and text | 1 vitest plus all existing E2E |
| Focus ring at least 3:1 | 1 contrast test plus MCP check |
| Dark theme follows the system | 1 E2E |
| 360 px, no horizontal scroll with long text | 4 E2E |
| Reduced motion | 4 E2E |
| Contrast at least 4.5:1 and 3:1 | 1 contrast test |
