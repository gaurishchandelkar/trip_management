# Tech Stack

| Area | Choice |
|---|---|
| Backend | Python 3.12+, FastAPI, Uvicorn, Pydantic |
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
| TypeScript `~6.0` | typescript-eslint supports only `<6.1` so far. Lift the pin, and the TypeScript ignore in `.github/dependabot.yml`, when it supports TypeScript 7 |
| No `eslint-plugin-react` | It doesn't support ESLint 10 yet. `dangerouslySetInnerHTML` is blocked with `no-restricted-syntax` instead |
| `httpx2` (test only) | Starlette's `TestClient` deprecated `httpx` in favor of `httpx2` |
| Two Playwrights | Python Playwright runs the E2E tests with its own Chromium. The Playwright MCP server (`@playwright/mcp`) bundles its own Playwright and uses the installed Chrome. The two never share a browser |
