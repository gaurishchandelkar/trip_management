# Coding Guidelines

## General

1. Keep it simple. Write the least code that meets the spec.
2. Add comments only to explain *why*, never *what*.
3. Avoid overly defensive code. Validate at system boundaries (HTTP input, external data) and trust internal code.
4. Name things after the domain, for example `get_greeting`, not `process_data`.
5. Keep the README short. No emojis in code or docs.

## Architecture

The backend has three layers. Each layer may import only from the layers below it.

```
api/       HTTP: routing, request/response models, status codes
services/  Use cases: orchestrate domain logic, no HTTP concepts
domain/    Pure types and rules: no FastAPI, no I/O
```

The frontend follows the same idea: components render, `api.ts` talks to the backend, and components never call `fetch` directly.

*Enforced by:* import-linter contracts in `pyproject.toml`, and ESLint `no-restricted-imports` / `no-restricted-globals` in `eslint.config.js`.

## Python

- Run everything through uv: `uv run ...`, never `python`, `pip` or `python3`. Add dependencies with `uv add`.
- Type-annotate all public functions. Use Pydantic models at the API boundary and dataclasses in `domain/`.
- *Enforced by:* `ruff format`, `ruff check` (including the bandit `S` rules) and `pyright` in strict mode.

## TypeScript / React

- Strict mode. Never use `any`, non-null assertions or `@ts-ignore`.
- Use function components and hooks. Model state as discriminated unions (see `App.tsx`).
- Never use `dangerouslySetInnerHTML`.
- *Enforced by:* `tsc`, ESLint (typescript-eslint strict, react-hooks) and Prettier.

## Tests

- Every behavior change comes with a test. Test behavior, not implementation.
- **Unit:** `backend/tests/unit/` (pytest) and `frontend/src/**/*.test.tsx` (vitest + Testing Library).
- **Integration:** `backend/tests/integration/` covers the HTTP API through all layers with `TestClient`.
- **Functional:** `e2e/` (pytest + Playwright) drives a fresh production build of the frontend against the real backend.
  - Every user journey gets an **outside** test in `test_journeys.py`, which asserts only what the user sees.
  - Every journey also gets an **inside** test in `test_network_contract.py`, which asserts the exact `/api/` calls through `ApiTraffic`: method, path, decoded query, status and body, with no unexpected extra calls.
  - Keep the two apart, so a contract break fails the inside test while the outside test still passes.
  - Wait for the page's initial state (the loaded greeting) before interacting, so the test never races the first request.
  - Wrap each action in `page.expect_response(...)` for the call it should cause, then assert. Don't use `networkidle`: it settles once per navigation, so it doesn't wait for calls caused by a later click. "No extra calls" covers calls made before the assertion. Never use sleeps.
- Tests are deterministic, with no real network calls, sleeps or order dependence.
- Assert through public interfaces: HTTP responses, the OpenAPI schema, the rendered DOM. Never assert on framework internals.
- Tests start the processes they verify and never reuse an already-running server. Use `127.0.0.1`, not `localhost`, because `localhost` can resolve to `::1`.
- *Enforced by:* the 80% line and branch coverage gates in `npm run check`.

## Suppressions

Don't add `# noqa`, `# type: ignore`, `# pyright: ignore`, `eslint-disable` or `@ts-expect-error`.
If a rule is wrong for a case, stop and ask. *Enforced by:* the guard hook and the `code-reviewer` subagent.
