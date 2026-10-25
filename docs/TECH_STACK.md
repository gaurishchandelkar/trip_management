# Tech Stack

| Area | Choice |
|---|---|
| Backend | Python 3.12+, FastAPI, Uvicorn, Pydantic |
| Storage | SQLite through SQLAlchemy 2.x Core, in `backend/storage/` only. The file comes from `TRIP_DB_PATH` (default `trip.db` in the repo root). The schema is created on startup, with no migrations yet |
| Python tooling | uv (deps and running), ruff (lint and format), pyright (types), pytest + pytest-cov, import-linter, pip-audit |
| Frontend | React 19, Vite, TypeScript (strict) |
| Frontend tooling | ESLint (typescript-eslint, react-hooks), Prettier, vitest + Testing Library |
| Functional tests | pytest + pytest-playwright (Chromium), against a `vite build` served by `vite preview` |
| Git hooks | lefthook |
| Secrets scanning | detect-secrets |
| CI | GitHub Actions, Dependabot |
| Agent harness | `AGENTS.md`, `CLAUDE.md`, `.claude/` (settings, hooks, skills, subagents), Playwright MCP |

The root `package.json` runs all tasks, and Python commands go through `uv run`.

## Version pins and substitutions

| What | Why |
|---|---|
| SQLAlchemy over SQLModel | SQLModel ties API models to tables, lags SQLAlchemy releases and types less cleanly under pyright strict. Plain SQLAlchemy keeps Pydantic API models, tables and domain dataclasses apart (`docs/plans/PLAN_members-and-groups.md`) |
| TypeScript `~6.0` | typescript-eslint supports only `<6.1` so far. Lift the pin, and the TypeScript ignore in `.github/dependabot.yml`, when it supports TypeScript 7 |
| No `eslint-plugin-react` | It doesn't support ESLint 10 yet. `dangerouslySetInnerHTML` is blocked with `no-restricted-syntax` instead |
| `httpx2` (test only) | Starlette's `TestClient` deprecated `httpx` in favor of `httpx2` |
| Two Playwrights | Python Playwright runs the E2E tests with its own Chromium. The Playwright MCP server (`@playwright/mcp`) bundles its own Playwright and uses the installed Chrome. The two never share a browser |
