# Status

## Current state

- **Product:** Trip Management members and groups (`docs/specs/members-and-groups.md`): register, sign in with a hashed session cookie (password field present but not checked yet), create groups, browse and search, ask to join from the list or by name, and owner approve or reject. SQLite storage through SQLAlchemy 2.x. The Hello World greeting is retired.
- **Rules:** `AGENTS.md`, `CLAUDE.md`, and the `docs/` rules and templates are in place.
- **Safeguards:**
  - ruff (including bandit rules), pyright strict, ESLint strict, Prettier and tsc
  - import-linter layer contracts (`api → services → storage → domain`, and SQLAlchemy only in `backend/storage`)
  - pip-audit, npm audit and detect-secrets
  - a scan for invisible Unicode format characters in tracked source (`scripts/harness-config.test.mjs`)
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

- **App shell and design system** (`docs/plans/PLAN_app-shell-and-design-system.md`), branch `feat/app-shell-and-design-system`.
  - Phase 1 done: design tokens with light and dark themes (`frontend/src/theme/`), reusable components (`frontend/src/ui/`), and every screen restyled with unchanged names, messages and API calls. A token contrast test and a raw-colour scan guard the theme.

## Known gaps

- `main` has no GitHub branch protection (private repo on a free plan). "Never commit straight to `main`" is enforced by a local pre-commit hook, so a merge or push made outside this clone isn't checked.
- The guard asks before shell writes that name check config or contain suppressions, but it matches command text, so a write it doesn't recognise still gets through.
- Passwords aren't checked yet (spec D1), so the app is for local, trusted use only until real authentication lands.
- Browsing stops at 50 groups with no paging; members narrow the list with search.
- The schema is created on startup with no migrations, so a later schema change needs a migration tool or a fresh database.
- The guard hook only inspects command text heuristically. It's a seatbelt, not a sandbox, and CI is the backstop.
  It covers the Bash and PowerShell tools. A new shell tool must be added to `SHELL_TOOLS` in `.claude/hooks/guard.mjs`, and a test checks that `.claude/settings.json` sends each one through the guard.
