# Status

## Current state

- **Product:** Trip Management members and groups (`docs/specs/members-and-groups.md`): create groups, browse and search, ask to join from the list or by name, and owner approve or reject. SQLite storage through SQLAlchemy 2.x. The Hello World greeting is retired.
- **Sign-in** (`docs/specs/sso-registration.md`): Google only, through OpenID Connect with PKCE (`backend/identity/`, joserfc + httpx2), then a hashed session cookie. New people finish registering with a user ID, display name and mobile number; members edit their display name and mobile on Profile. Display names show with `@user-id` beside them, and only a group's owner sees mobile numbers. The user-ID and unchecked-password forms are retired.
- **Frontend:** branded **Caravan** (`docs/specs/app-shell-and-design-system.md`): an app shell with skip link and per-screen titles, `react-router` addresses (`/`, `/groups/{id}`, `/profile`, `/register/complete`, not found), modal dialogs for creating and joining groups, and a plain-CSS design system (`frontend/src/theme/`, `frontend/src/ui/`) with light and dark themes, a self-hosted Inter font, reduced-motion support and phone layouts down to 360 px.
- **Rules:** `AGENTS.md`, `CLAUDE.md`, and the `docs/` rules and templates are in place.
- **Safeguards:**
  - ruff (including bandit rules), pyright strict, ESLint strict, Prettier and tsc
  - import-linter layer contracts (`api → services → storage | identity → domain`, SQLAlchemy only in `backend/storage`, and httpx2 and joserfc only in `backend/identity`)
  - pip-audit, npm audit and detect-secrets
  - a scan for invisible Unicode format characters in tracked source (`scripts/harness-config.test.mjs`)
  - a design-token contrast test (WCAG AA, both themes) and a scan that keeps raw colours out of every stylesheet but `tokens.css` (`frontend/src/theme/tokens.test.ts`)
  - a scan that fails on any third-party URL in the frontend's sources (`frontend/src/origins.test.ts`)
  - a check that every plan's "Spec coverage" table names real tests as `path::test name` (`scripts/harness-config.test.mjs`)
  - checks that every script CI runs has a test that spawns it (`scripts/check.test.mjs` for the pipeline), that frontend tests wait for the tab title (`expectTitle`), and that E2E browsers come from pytest-playwright's fixtures, so a failure keeps its trace (`scripts/harness-config.test.mjs`)
  - lefthook pre-commit
  - Claude Code permission rules, guard hook and format hook
- **Verification:** `npm run check` runs build → lint → unit → integration → functional → security → architecture.
  - Coverage gates are at 80%.
  - E2E runs on dedicated ports, so a running dev server is never what gets tested.
  - E2E is pytest + Playwright against a fresh production build. Each journey has an outside test (what the user sees) and an inside test (the exact API calls, via `e2e/network.py`), paired with `@covers` and checked by `scripts/harness-config.test.mjs`.
  - E2E signs people in through a fake Google (`e2e/fake_google.py`, port 8102) that issues real RS256 ID tokens. The traffic check allows that one extra origin.
  - `e2e/test_screenshots.py` captures 24 screenshots of the main screens against its own servers (ports 8101 and 5274) with fixed sample data.
- **CI:** GitHub Actions runs one job per stage. The functional job uploads the screenshots as `ui-screenshots` on every run, kept 14 days, and lists them in its job summary (`scripts/screenshot-summary.mjs`). `npm run pr` attaches the same 24 captures to a PR that changes the UI, refusing a partial or stale set, and opens PRs with or without a spec. Dependabot and CODEOWNERS are configured. GitHub doesn't protect `main`: the repo is private on a free plan, so GitHub refuses branch protection (403). A lefthook pre-commit job (`scripts/refuse-main.mjs`) refuses local commits on `main` instead. Once the plan changes, `scripts/protect-branch.mjs --solo` requires PRs, an up-to-date branch and all 7 CI checks, admins included.
- **Staged autonomy:** the `/spec`, `/plan`, `/implement`, `/ship` and `/retro` skills, the `code-reviewer` and `security-reviewer` subagents, and the PR template.
- **Flywheel and metrics:** `docs/HARNESS_LOG.md`, `docs/METRICS.md` and `npm run metrics`.
- **Reference example:** `docs/specs/personalised-greeting.md` and `docs/plans/PLAN_personalised-greeting.md`.

## In progress

- **Registration and sign-in with Google** (`docs/specs/sso-registration.md`, `docs/plans/PLAN_sso-registration.md`), on `feat/sso-registration`.
  - Phase 1 done: the OpenID Connect adapter (`backend/identity/`, joserfc + httpx2), PKCE, and an import contract that keeps `httpx2` and `joserfc` inside `backend/identity`.
  - Phase 2 done: the backend sign-in and registration API (`/api/auth/...`) and the `identities`, `sign_in_flows` and `pending_registrations` tables. Google is on when `TRIP_GOOGLE_CLIENT_ID` and `TRIP_GOOGLE_CLIENT_SECRET` are set.
  - Phase 3 done: the app signs people in only with **Continue with Google**, and new people pick a user ID, display name and mobile number on **Finish registering** (`/register/complete`). `POST /api/members` and `POST /api/sign-in` are gone, and `members.mobile` is required. An old `trip.db` stops startup with a message to delete it. E2E signs in through a fake Google (`e2e/fake_google.py`, port 8102).
  - Phase 4 done: every person shows their display name with `@user-id` beside it (banner, cards, members, requests, Approve/Reject labels). Group detail carries `user_id`, groups carry `owner_user_id`, and only a group's owner gets mobile numbers, shown as `tel:` links.
  - Phase 5 done: **Profile** (`/profile`, `POST /api/me/profile`) edits the display name and mobile; the screenshot set is 24 images; docs updated. Left for `/ship`: `code-reviewer` and `security-reviewer`. Left for the human: a real Google sign-in on `localhost`, and adding the variable names to `.env.example`.

## Known gaps

- `main` has no GitHub branch protection (private repo on a free plan). "Never commit straight to `main`" is enforced by a local pre-commit hook, so a merge or push made outside this clone isn't checked.
- The guard asks before shell writes that name check config or contain suppressions, but it matches command text, so a write it doesn't recognise still gets through.
- The app is for local use: it runs over plain HTTP, its cookies aren't `Secure`, and there's no deployment. Sign-in is only as strong as that.
- Real Google sign-in is checked by hand only. CI and `npm run check` sign in through the fake provider, which follows the protocol but isn't Google.
- Mobile numbers aren't verified, and nothing stops a member from typing someone else's.
- Browsing stops at 50 groups with no paging; members narrow the list with search.
- The frontend's size budgets (150 KB of gzipped JS, 100 KB of font) were checked once when the design system landed (87 KB and 48 KB) and aren't gated in `npm run check`, so growth goes unnoticed until someone measures again.
- The schema is created on startup with no migrations, so a later schema change needs a migration tool or a fresh database.
- The guard hook only inspects command text heuristically. It's a seatbelt, not a sandbox, and CI is the backstop.
  It covers the Bash and PowerShell tools. A new shell tool must be added to `SHELL_TOOLS` in `.claude/hooks/guard.mjs`, and a test checks that `.claude/settings.json` sends each one through the guard.
