# Plan: Python E2E tests with whitebox verification

Spec: `docs/specs/python-e2e-whitebox.md`
Status: **Done**

## Approach

Test infrastructure changes; no production code changes.
A pytest session fixture in `e2e/conftest.py` builds the frontend into a fresh temporary folder, then starts uvicorn on `127.0.0.1:8100` and `vite preview` on `127.0.0.1:5273`, which proxies `/api` to the backend. It fails fast if a port is busy, a server isn't healthy within 30 s, or a server dies.
Outside tests drive the page through pytest-playwright and assert only what the user sees.
Inside tests use a small traffic recorder (`e2e/network.py`) that captures every request and response from Playwright events. They assert the exact `/api/` calls (method, path, decoded query, status, body), and the recorder's teardown fails any test that touched an origin other than the preview server.

Main trade-off: building into a fresh folder adds about 5 s per session. It guarantees the tests never drive a stale `dist/`, the same failure class as the stale dev server in the harness log.
The production build also matters for correctness. `main.tsx` uses `StrictMode`, which runs effects twice in dev mode, so "exactly one request on load" would fail against the dev server even though shipped code is correct.

## Human attention needed

- **New dependency (approved):** `pytest-playwright` as a dev dependency, which brings in `playwright`. Version 0.10 provides its own `base_url` fixture, so `pytest-base-url` isn't needed. Python Playwright downloads its own Chromium (about 150 MB), installed by `scripts/prepare.mjs` and in CI with `uv run playwright install`.
- **Rule exclusion (approved during Phase 1):** ruff's bandit rule S603 flags every subprocess call. The human approved a per-file ignore for `e2e/conftest.py` only, which starts the servers under test with a fixed argv. S603 stays on everywhere else.
- **Install order:** `scripts/prepare.mjs` calls `uv run --frozen playwright install chromium`, so `npm install` needs `uv` on PATH. `uv run` installs the locked Python deps itself if `uv sync` hasn't run yet. (Corrected after code review: an earlier draft said `uv sync` had to run first.)
- **Protected files, for your review in the PR:**
  - `.github/workflows/ci.yml`: the functional job installs Chromium with `uv run playwright install --with-deps chromium`. Job and check names are unchanged.
  - `.claude/settings.json`: remove the `Bash(npx playwright test *)` allow rule. `Bash(uv run pytest *)` already covers the new suite.
- **Small addition the spec implies but doesn't name:** `scripts/metrics.mjs` counts E2E tests by matching `test(` in `.spec.ts` files. It would report 0 after the switch, so it will count `def test_` in `e2e/*.py` instead.
- **`docs/SPEC.md`:** the product doesn't change, so I'll leave it as is even though the spec's Definition of Done lists it. Tell me if you want a note there.
- **Playwright MCP:** it bundles its own Playwright and uses the installed Chrome by default (`--browser` defaults to the chrome channel). It never used the Chromium that `@playwright/test` installed, so removing that package doesn't affect it.
- **Spec mapping:** the four outside journeys and the four request-level inside checks are separate tests, so a whitebox failure shows up alone while the matching black-box test passes. The spec's "every request accounted for" criterion is enforced in two places: the exact-call assertions in each inside test, and the foreign-origin check at teardown in every test.

## Phase 1: Python E2E servers and outside journeys

- Add `pytest-playwright` with `uv add --dev`.
- `pyproject.toml`: add `e2e` to the pyright `include`, and add an `e2e/**` ruff per-file ignore for `S101` (asserts), matching `backend/tests/**`. Also ignore `S603` for `e2e/conftest.py` only, as approved.
- Add `e2e/conftest.py`:
  - a session fixture that builds into `tmp_path_factory` with `vite build frontend --outDir <tmp> --emptyOutDir`, then starts uvicorn and `vite preview --outDir <tmp> --strictPort`
  - a busy-port check before startup, and health polling with a 30 s limit that shows the server's output on failure
  - a `base_url` override, and an autouse check that both servers are still alive before each test
- Add `e2e/test_journeys.py` with the four outside tests: `test_shows_default_greeting`, `test_shows_alert_when_backend_fails`, `test_greets_entered_name` and `test_rejects_markup_without_rendering_it`.
- The TypeScript suite stays the `functional` stage until Phase 3, so the checks stay green.

Success criteria:
- [x] `uv run pytest e2e` reports 4 passed
- [x] With something listening on `127.0.0.1:8100`, the session errors naming port 8100, and no test runs against the foreign server
- [x] With a broken uvicorn target, the session fails naming the backend and showing its output, well before the 30 s limit (the process exits)
- [x] With `PLAYWRIGHT_BROWSERS_PATH` set to an empty folder, the run fails with Playwright's message naming `playwright install`
- [x] A temporary scratch test that kills the preview server makes the next test fail with "frontend server is not running". The scratch test isn't committed
- [x] `npm run check` passes

## Phase 2: Network contract (whitebox)

- Add `e2e/network.py` with an `ApiTraffic` recorder. It captures each request (method, URL, origin, path, decoded query) and its response (status, JSON or text body) through `page.on("request")` and `page.on("response")`. An `api_calls()` view filters to `/api/`, and failure messages list every call seen.
- In `e2e/conftest.py`, add an autouse `traffic` fixture. At teardown it fails the test if any request went to an origin other than `http://127.0.0.1:5273`.
- Add `e2e/test_network_contract.py` with four tests:
  - `test_load_requests_default_greeting_once`
  - `test_greet_sends_trimmed_name_once`
  - `test_greet_sends_full_name_intact`
  - `test_markup_gets_generic_422_without_echo`

  Each waits for network idle, then asserts the exact list of `/api/` calls.

Success criteria:
- [x] `uv run pytest e2e` reports 8 passed
- [x] **Mutation proof:** a temporary change makes `frontend/src/api.ts` fetch the greeting twice. Then `test_load_requests_default_greeting_once` fails, listing both calls, while `test_shows_default_greeting` still passes. The output is recorded in the PR and the change is reverted
- [x] **Foreign-origin proof:** a temporary scratch test requests `http://localhost:9/`. Teardown fails it, naming that origin. The scratch test isn't committed
- [x] `npm run check` passes

## Phase 3: Cut over the functional stage

- `package.json`: `test:e2e` becomes `uv run pytest e2e --browser chromium --tracing retain-on-failure --screenshot only-on-failure --output test-results`. Remove `@playwright/test` with `npm uninstall`.
- Delete `e2e/hello.spec.ts` and `playwright.config.ts`, and drop `e2e` and `*.config.ts` from the `tsconfig.json` `include`.
- `scripts/prepare.mjs`: outside CI, run `uv run playwright install chromium` instead of `npx playwright install chromium`.
- `.github/workflows/ci.yml`: the functional job runs `uv run playwright install --with-deps chromium`, and still uploads `test-results/` on failure.
- `.claude/settings.json`: remove the `Bash(npx playwright test *)` allow rule.
- `scripts/metrics.mjs`: count E2E tests as `def test_` in `e2e/**/*.py`.

Success criteria:
- [x] `npm run check` passes, and the functional stage runs the 8 Python tests in under 30 s
- [x] `npm ls @playwright/test` shows nothing, and `git ls-files e2e` lists only Python files
- [x] `npm run metrics` reports 8 e2e tests
- [x] A deliberately failing E2E test leaves a trace and a screenshot under `test-results/`. It's reverted afterwards
- [x] CI's `functional` job passes on the PR, in under 90 s (49 s on PR #6)

## Phase 4: Docs

- `docs/TECH_STACK.md`: pytest-playwright for E2E, and the Playwright MCP's separate browser.
- `docs/PROCESS.md`: the functional stage row (Python E2E, production build, outside and inside checks).
- `docs/CODING_GUIDELINES.md`: an E2E test rule. Every journey gets an outside test, and an inside test asserting the exact API calls through `ApiTraffic`. No sleeps.
- `README.md`, `AGENTS.md` (repo map: `e2e/` is pytest + Playwright) and `docs/STATUS.md`.
- Tick the spec's acceptance criteria.

Success criteria:
- [x] `grep -rn "hello.spec.ts\|@playwright/test\|playwright.config" docs README.md AGENTS.md CLAUDE.md` finds only historical `HARNESS_LOG.md` and `PLAN.md` entries
- [x] `npm run check` passes

## Final verification

- [x] `npm run check` passes
- [x] Every acceptance criterion in the spec is covered by a test:
  - outside journeys 1–4 map to `test_journeys.py`
  - inside checks 1–4 map to `test_network_contract.py`
  - inside check 5 maps to the exact-call assertions plus the foreign-origin teardown
- [x] Every failure condition in the spec has a recorded check from Phase 1 or 2
