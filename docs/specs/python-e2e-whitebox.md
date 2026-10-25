# Spec: Python E2E tests with whitebox verification

Status: **Done**

## Expected outcome

The functional stage runs Python E2E tests (pytest + Playwright) instead of the TypeScript `@playwright/test` suite.
Each user journey is checked from the outside (what the user sees) and from the inside (the exact requests the browser sent and the responses the backend returned), so a test can't pass by accident while the frontend and backend talk to each other the wrong way.

## Constraints

- **Behavior stays the same.** The four journeys in `e2e/hello.spec.ts` keep their assertions: default greeting, backend failure alert, greeting a name, and rejecting markup without rendering it.
- **Same stage, same name.** The `functional` stage in `npm run check` and the `functional` CI job stay, so branch protection's required checks are unchanged.
- **Isolation stays.** Tests start their own servers on dedicated ports, bind to `127.0.0.1`, and never reuse a running dev server (`docs/CODING_GUIDELINES.md`, harness log "E2E verified a stale dev server").
- **Whitebox through the network only.** Inside checks observe the browser's traffic with Playwright request and response events. They don't touch backend internals, and no production code changes (`docs/CODING_GUIDELINES.md`: assert through public interfaces; the HTTP API is the public interface between frontend and backend).
- **Layering stays.** E2E code imports nothing from `backend/` or `frontend/`, and import-linter contracts are unchanged.
- **The agent's browser stays.** The Playwright MCP server (`.mcp.json`, `@playwright/mcp`) is separate and unaffected.
- **New dependency:** `pytest-playwright` (it brings in `playwright`). Security guidelines require human approval; see Decisions.
- **Protected files:** `.github/workflows/ci.yml` and `.claude/settings.json` change, so they need human approval in the PR.

## Acceptance criteria

### Outside (black-box), ported from `e2e/hello.spec.ts`

- [x] Given the app is running, when the page loads, then the heading reads "Hello, World!"
- [x] Given `/api/hello` returns 500, when the page loads, then an alert reads "Could not load greeting"
- [x] Given the page has loaded, when the user enters "Ada" and clicks Greet, then the heading reads "Hello, Ada!"
- [x] Given the page has loaded, when the user submits `<script>alert(1)</script>`, then an alert reads "Please enter a valid name", `main` contains no `script` element, and no dialog opens

### Inside (whitebox): network contract

- [x] Given the page loads, then the browser sends exactly one `GET /api/hello` with no query string, and it returns 200 `{"message": "Hello, World!"}`
- [x] Given the user greets "  Ada  ", then the browser sends exactly one `GET /api/hello?name=Ada` (trimmed), and it returns 200 `{"message": "Hello, Ada!"}`
- [x] Given the user greets "Ada Lovelace", then the `name` query parameter decodes to exactly `Ada Lovelace`, and the response message is "Hello, Ada Lovelace!"
- [x] Given markup is submitted, then the response is 422 `{"detail": "Invalid request"}`, and its body doesn't contain the submitted input
- [x] Given any journey above, then every request the page makes to `/api/` is accounted for: no unexpected extra calls, and no request to any origin other than the test servers

## Non-functional requirements

- **Speed:** the functional stage stays under 30 s locally and 90 s in CI (it's about 12 s and 48 s today).
- **Determinism:** no fixed sleeps. Use Playwright's auto-waiting, and expected-request and expected-response waits.
- **Diagnosability:** a failing test keeps a Playwright trace and screenshot in `test-results/`, and CI uploads that folder.
- **Security:** no binding to `0.0.0.0`, and no secrets in tests. The new Python dependencies pass pip-audit.
- **Quality bar:** E2E Python code passes ruff, pyright strict and the guard's suppression ban, like other Python.

## Failure conditions

- **A test port is busy:** the session fails immediately and names the port. It never tests whatever is listening there.
- **A server doesn't become healthy within 30 s:** the session fails, names the server, and shows its output. It doesn't hang.
- **The Chromium browser isn't installed:** the session fails with the command to install it.
- **The frontend server dies mid-run:** the remaining tests fail rather than pass against nothing.
- **A whitebox observation doesn't match** (an expected request never came, came twice, or carried the wrong query): the test fails, listing the expected request and the requests actually seen.

## Definition of Done

- [ ] All acceptance criteria are covered by passing tests
- [ ] `npm run check` passes, and the CI `functional` job passes on a PR
- [ ] `docs/SPEC.md` and `docs/STATUS.md` are updated
- [ ] `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/CODING_GUIDELINES.md`, `README.md` and `AGENTS.md` describe the Python E2E suite and its whitebox checks
- [ ] `scripts/prepare.mjs` and CI install Chromium for the Python Playwright
- [ ] A deliberately broken journey (for example, the frontend fetching the greeting twice) fails an inside check while the outside check still passes. That shows the whitebox layer catches what black-box misses.

## Out of scope

- Browsers other than Chromium, visual regression, accessibility audits and load tests
- Changing product behavior, or the unit and integration suites
- Whitebox checks on backend internals (service calls, in-process server) and backend or frontend coverage from E2E runs. The human chose network-contract checks only.

## Decisions

1. **Whitebox scope:** the network contract only (answered).
2. **Replace or run alongside:** replace (answered). Remove `e2e/*.spec.ts`, `playwright.config.ts` and `@playwright/test`, and add `pytest-playwright`.
3. **Frontend under test:** the production build (answered). Run `vite build`, then `vite preview` on a dedicated port, proxying `/api` to the test backend.
4. **New dependency `pytest-playwright`:** approved by the human.
