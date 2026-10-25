# Plan: Hyper-Productivity Harness Template

A ready-to-use template repo (Hello World React + FastAPI) that implements the Agentic Harness
described in [AI Agents in the Fast Lane: Engineering for Hyper Productivity](https://medium.com/@gaurish-chandelkar/ai-agents-in-the-fast-lane-engineering-for-hyper-productivity-fcbcd902ee9a).

## Design principles

| Article concept | Repo realisation |
|---|---|
| Rules guide | `RULES.md`, `CODING_GUIDELINES.md`, `PROCESS.md`, `SECURITY_GUIDELINES.md`, loaded via `AGENTS.md` / `CLAUDE.md` |
| Safeguards protect | Pre-commit hooks, linters, type checks, security scans, architecture rules, agent permission rules, branch protection |
| Verification provides evidence | Unit, integration and E2E tests with coverage gates, one `npm run check` |
| Better specifications | Agent-ready spec template: outcome, constraints, acceptance criteria, NFRs, failure conditions, Definition of Done |
| Staged autonomy | Spec → Plan → human approval → Implement → Verify → PR, each producing an artifact |
| Autonomy follows verification | Build → Lint → Unit → Integration → Functional → Security → Architecture, identical locally, in hooks and in CI |
| Flywheel | `/retro` skill + `HARNESS_LOG.md` turning each failure into a test, rule, safeguard or skill |
| Time to Validated Outcome | Metrics doc + script over git/PR history |

## Defaults

- Cross-tool, Claude Code first: `AGENTS.md` is the source of truth, `CLAUDE.md` imports it.
- lefthook for git hooks, GitHub for CI, branch protection and PR metrics.
- Python 3.12+ via uv only, Node 22+, React 19, Vite, TypeScript strict. Everything works on Windows.

## Iteration 1: Foundation and Hello World

- Git repo, `.gitignore`, `.gitattributes`, `.python-version`, `.nvmrc`
- FastAPI backend with `GET /api/health` and `GET /api/hello`, layered `api/` → `services/` → `domain/`
- React + Vite + TS frontend calling `/api/hello` via the Vite proxy
- `npm run dev` starts both; short README

Success criteria:
- [x] `uv sync && npm install && npm run dev` works on a fresh clone
- [x] `/api/hello` returns JSON and the page renders the message

## Iteration 2: Rules layer

- `AGENTS.md` (entry point), `CLAUDE.md` (imports `@AGENTS.md`)
- `docs/RULES.md`, `CODING_GUIDELINES.md`, `PROCESS.md`, `SECURITY_GUIDELINES.md`
- `docs/SPEC.md`, `TECH_STACK.md`, `STATUS.md`
- `docs/templates/SPEC_TEMPLATE.md` with a worked example

Success criteria:
- [x] All four rule files exist and are referenced from `AGENTS.md` in a required reading order
- [x] Every enforceable rule names the safeguard or check that enforces it

## Iteration 3: Safeguards

- Backend: ruff (lint, format, bandit `S` rules), pyright strict
- Frontend: ESLint (typescript-eslint strict, react-hooks), Prettier, `tsc`
- Architecture rules: import-linter (api → services → domain), ESLint import boundaries
- Dependency and security: pip-audit, npm audit, detect-secrets
- lefthook pre-commit: format staged files, then lint and types for the side that changed
- Agent safeguards in `.claude/`: permission denies, `PreToolUse` guard hook, `PostToolUse` format hook

Success criteria:
- [x] A lint error, type error, hard-coded secret or reversed layer import fails the checks
- [x] The guard hook blocks `git push`, `--no-verify`, `.env` access and suppression comments

## Iteration 4: Verification pipeline

- Unit: pytest and vitest + Testing Library, 80% coverage gates
- Integration: FastAPI `TestClient` across all layers
- Functional: Playwright E2E against both servers
- `npm run check` runs build → lint → unit → integration → functional → security → architecture
- `.mcp.json` with the Playwright MCP server
- GitHub Actions workflow mirroring the stages, Dependabot, CODEOWNERS, branch protection script

Success criteria:
- [x] `npm run check` passes locally and a broken test fails it at the right stage
- [x] CI workflow defines one job per stage

## Iteration 5: Staged autonomy workflow

- Skills: `/spec`, `/plan`, `/implement`, `/ship`
- Subagents: `code-reviewer`, `security-reviewer`
- PR template with spec link, Definition of Done, verification evidence and "human attention needed"

Success criteria:
- [x] Each skill and subagent is defined with clear stop points for human approval
- [x] `/plan` writes a plan file and stops without touching code

## Iteration 6: Flywheel, metrics and end-to-end proof

- `docs/HARNESS_LOG.md` and a `/retro` skill using the feedback-signal → harness-improvement table
- `docs/METRICS.md` and `scripts/metrics.mjs`
- Dogfood feature: personalised greeting `GET /api/hello?name=` through spec → plan → implement → retro
- Template-ise: README walkthrough, `scripts/init-project.mjs`

Success criteria:
- [x] The example feature ships with spec, plan and passing checks
- [x] `/retro` is documented with a real harness-log entry and `metrics.mjs` prints a report
- [x] `npm run check` passes after `init-project.mjs`
