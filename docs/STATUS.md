# Status

## Current state

- **Product:** a Hello World backend and frontend with a personalised greeting (`/api/hello?name=`), with server-side allow-list validation and a generic 422 response.
- **Rules:** `AGENTS.md`, `CLAUDE.md`, and the `docs/` rules and templates are in place.
- **Safeguards:**
  - ruff (including bandit rules), pyright strict, ESLint strict, Prettier and tsc
  - import-linter layer contracts
  - pip-audit, npm audit and detect-secrets
  - lefthook pre-commit
  - Claude Code permission rules, guard hook and format hook
- **Verification:** `npm run check` runs build → lint → unit → integration → functional → security → architecture.
  - Coverage gates are at 80%.
  - E2E runs on dedicated ports, so a running dev server is never what gets tested.
  - E2E is pytest + Playwright against a fresh production build. Each journey has an outside test (what the user sees) and an inside test (the exact API calls, via `e2e/network.py`).
- **CI:** GitHub Actions runs one job per stage. Dependabot and CODEOWNERS are configured. `main` is protected with `scripts/protect-branch.mjs --solo`: PRs, an up-to-date branch and all 7 CI checks are required, admins included.
- **Staged autonomy:** the `/spec`, `/plan`, `/implement`, `/ship` and `/retro` skills, the `code-reviewer` and `security-reviewer` subagents, and the PR template.
- **Flywheel and metrics:** `docs/HARNESS_LOG.md`, `docs/METRICS.md` and `npm run metrics`.
- **Reference example:** `docs/specs/personalised-greeting.md` and `docs/plans/PLAN_personalised-greeting.md`.

## In progress

- None.

## Known gaps

- The guard hook only inspects command text heuristically. It's a seatbelt, not a sandbox, and CI is the backstop.
  It covers the Bash and PowerShell tools. A new shell tool must be added to `SHELL_TOOLS` in `.claude/hooks/guard.mjs`, and a test checks that `.claude/settings.json` sends each one through the guard.
