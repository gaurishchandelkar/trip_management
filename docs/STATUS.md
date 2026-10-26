# Status

## Current state

- **Product:** Trip Management members and groups (`docs/specs/members-and-groups.md`): register, sign in with a hashed session cookie (password field present but not checked yet), create groups, browse and search, ask to join from the list or by name, and owner approve or reject. SQLite storage through SQLAlchemy 2.x. The Hello World greeting is retired.
- **Frontend:** branded **Caravan** (`docs/specs/app-shell-and-design-system.md`): an app shell with skip link and per-screen titles, `react-router` addresses (`/`, `/groups/{id}`, not found), modal dialogs for creating and joining groups, and a plain-CSS design system (`frontend/src/theme/`, `frontend/src/ui/`) with light and dark themes, a self-hosted Inter font, reduced-motion support and phone layouts down to 360 px.
- **Rules:** `AGENTS.md`, `CLAUDE.md`, and the `docs/` rules and templates are in place.
- **Safeguards:**
  - ruff (including bandit rules), pyright strict, ESLint strict, Prettier and tsc
  - import-linter layer contracts (`api → services → storage → domain`, and SQLAlchemy only in `backend/storage`)
  - pip-audit, npm audit and detect-secrets
  - a scan for invisible Unicode format characters in tracked source (`scripts/harness-config.test.mjs`)
  - a design-token contrast test (WCAG AA, both themes) and a scan that keeps raw colours out of every stylesheet but `tokens.css` (`frontend/src/theme/tokens.test.ts`)
  - a scan that fails on any third-party URL in the frontend's sources (`frontend/src/origins.test.ts`)
  - a check that every plan's "Spec coverage" table names real tests as `path::test name` (`scripts/harness-config.test.mjs`)
  - lefthook pre-commit
  - Claude Code permission rules, guard hook and format hook
- **Verification:** `npm run check` runs build → lint → unit → integration → functional → security → architecture.
  - Coverage gates are at 80%.
  - E2E runs on dedicated ports, so a running dev server is never what gets tested.
  - E2E is pytest + Playwright against a fresh production build. Each journey has an outside test (what the user sees) and an inside test (the exact API calls, via `e2e/network.py`), paired with `@covers` and checked by `scripts/harness-config.test.mjs`.
- **CI:** GitHub Actions runs one job per stage. Dependabot and CODEOWNERS are configured. GitHub doesn't protect `main`: the repo is private on a free plan, so GitHub refuses branch protection (403). A lefthook pre-commit job (`scripts/refuse-main.mjs`) refuses local commits on `main` instead. Once the plan changes, `scripts/protect-branch.mjs --solo` requires PRs, an up-to-date branch and all 7 CI checks, admins included.
- **Staged autonomy:** the `/spec`, `/plan`, `/implement`, `/ship` and `/retro` skills, the `code-reviewer` and `security-reviewer` subagents, and the PR template.
- **Flywheel and metrics:** `docs/HARNESS_LOG.md`, `docs/METRICS.md` and `npm run metrics`.
- **Reference example:** `docs/specs/personalised-greeting.md` and `docs/plans/PLAN_personalised-greeting.md`.

## In progress

- **CI screenshot artifacts** (`docs/plans/PLAN_ci-screenshot-artifacts.md`), branch `feat/ci-screenshot-artifacts`.
  - Phase 1 done: `e2e/test_screenshots.py` captures 20 screenshots (5 screens, light and dark, 360 and 1280 px) into `test-results/screenshots/`. It uses its own backend and preview server (ports 8101 and 5274) and fixed sample data.

## Known gaps

- `main` has no GitHub branch protection (private repo on a free plan). "Never commit straight to `main`" is enforced by a local pre-commit hook, so a merge or push made outside this clone isn't checked.
- The guard asks before shell writes that name check config or contain suppressions, but it matches command text, so a write it doesn't recognise still gets through.
- Passwords aren't checked yet (spec D1), so the app is for local, trusted use only until real authentication lands.
- Browsing stops at 50 groups with no paging; members narrow the list with search.
- The frontend's size budgets (150 KB of gzipped JS, 100 KB of font) were checked once when the design system landed (87 KB and 48 KB) and aren't gated in `npm run check`, so growth goes unnoticed until someone measures again.
- The schema is created on startup with no migrations, so a later schema change needs a migration tool or a fresh database.
- The guard hook only inspects command text heuristically. It's a seatbelt, not a sandbox, and CI is the backstop.
  It covers the Bash and PowerShell tools. A new shell tool must be added to `SHELL_TOOLS` in `.claude/hooks/guard.mjs`, and a test checks that `.claude/settings.json` sends each one through the guard.
