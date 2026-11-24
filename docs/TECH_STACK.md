# Tech Stack

| Area | Choice |
|---|---|
| Backend | Python 3.12+, FastAPI, Uvicorn, Pydantic |
| Storage | SQLite through SQLAlchemy 2.x Core, in `backend/storage/` only. The file comes from `TRIP_DB_PATH` (default `trip.db` in the repo root). The schema is created on startup, with no migrations yet |
| Sign-in | Google through OpenID Connect, in `backend/identity/` only: joserfc checks the ID token, httpx2 calls discovery, the token endpoint and the keys. Configured by `TRIP_GOOGLE_CLIENT_ID`, `TRIP_GOOGLE_CLIENT_SECRET`, optionally `TRIP_PUBLIC_URL` (default `http://localhost:5173`) and, for tests only, `TRIP_GOOGLE_ISSUER` (`https`, or `http` on `127.0.0.1` or `localhost`). Tests use an in-process fake (integration) and `e2e/fake_google.py` (E2E) |
| Python tooling | uv (deps and running), ruff (lint and format), pyright (types), pytest + pytest-cov, import-linter, pip-audit |
| Frontend | React 19, Vite, TypeScript (strict), React Router 8 (declarative mode) |
| Design system | Plain CSS: design tokens in `frontend/src/theme/tokens.css` (light and dark), components in `frontend/src/ui/`, the Inter variable font self-hosted through `@fontsource-variable/inter` |
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
| `react-router` 8.x | URLs for each screen. Declarative mode only (`BrowserRouter`, `Routes`), so data loading stays in components and the pinned E2E network contract is unchanged. It needs Node 22.22+, which `.nvmrc` (24) meets (`docs/plans/PLAN_app-shell-and-design-system.md`) |
| `@fontsource-variable/inter` | The font is bundled by Vite and served from the app's own origin. The E2E fixture fails on any third-party request, and a CDN font would leak visits. Browsers fetch only the subsets a page uses (Latin: 48 KB) |
| No UI kit, icon library, data-fetching library or CSS framework | Native `<dialog>` gives modality, Escape and focus return. A handful of hand-written SVG icons cover the screens. Plain fetch through `api.ts` keeps the exact call sequences the inside E2E tests pin, which a caching library's background refetching would change. A raw-colour scan and a contrast test keep plain CSS on the tokens |
| SQLAlchemy over SQLModel | SQLModel ties API models to tables, lags SQLAlchemy releases and types less cleanly under pyright strict. Plain SQLAlchemy keeps Pydantic API models, tables and domain dataclasses apart (`docs/plans/PLAN_members-and-groups.md`) |
| TypeScript `~6.0` | typescript-eslint supports only `<6.1` so far. Lift the pin, and the TypeScript ignore in `.github/dependabot.yml`, when it supports TypeScript 7 |
| No `eslint-plugin-react` | It doesn't support ESLint 10 yet. `dangerouslySetInnerHTML` is blocked with `no-restricted-syntax` instead |
| `httpx2` | Starlette's `TestClient` deprecated `httpx` in favor of `httpx2`, and the OIDC adapter uses the same client at runtime, so there's one HTTP library |
| joserfc over Authlib | Authlib's OAuth client ships no type information and fails `pyright --strict` without suppressions. joserfc, Authlib's own JOSE library by the same author, is typed. The authorization URL and PKCE are about 40 lines of our own, in `backend/identity/oidc.py` and `backend/domain/pkce.py` (`docs/plans/PLAN_sso-registration.md`) |
| Two Playwrights | Python Playwright runs the E2E tests with its own Chromium. The Playwright MCP server (`@playwright/mcp`) bundles its own Playwright and uses the installed Chrome. The two never share a browser |
