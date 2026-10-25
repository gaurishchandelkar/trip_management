# Hyper Harness

A ready-to-use template for **agentic hyper productivity**: a minimal React + FastAPI app inside the Agentic Harness from
[AI Agents in the Fast Lane: Engineering for Hyper Productivity](https://medium.com/@gaurish-chandelkar/ai-agents-in-the-fast-lane-engineering-for-hyper-productivity-fcbcd902ee9a).

> Safe autonomy ∝ verifiability. The model doesn't unlock hyper productivity on its own. The system around it does.

## What's in the harness

| Pillar | What it is | Where |
|---|---|---|
| **Rules guide** | Operating rules, coding and security guidelines, the staged process | `AGENTS.md`, `CLAUDE.md`, `docs/RULES.md`, `docs/CODING_GUIDELINES.md`, `docs/PROCESS.md`, `docs/SECURITY_GUIDELINES.md` |
| **Safeguards protect** | ruff (with bandit rules), pyright strict, ESLint strict, Prettier, import-linter layer contracts, pip-audit, npm audit, detect-secrets, lefthook pre-commit, agent permission rules and guard hook, branch protection | `pyproject.toml`, `eslint.config.js`, `lefthook.yml`, `.claude/`, `scripts/protect-branch.mjs` |
| **Verification gives evidence** | Unit and integration tests with 80% coverage gates, and Python Playwright E2E tests that check both the UI and the exact API calls behind it, in one pipeline locally and in CI | `npm run check`, `.github/workflows/ci.yml` |
| **Better specs** | Agent-ready spec and plan templates | `docs/templates/` |
| **Staged autonomy** | `/spec` → `/plan` → *human approves* → `/implement` → `/ship` → *human merges* → `/retro` | `.claude/skills/`, `.claude/agents/` |
| **Flywheel** | Each failure becomes a test, rule, safeguard or skill | `docs/HARNESS_LOG.md`, `/retro` |
| **Metrics** | Time to validated outcome, first-pass rate, rework, harness growth | `docs/METRICS.md`, `npm run metrics` |

## Use this template

Prerequisites: [uv](https://docs.astral.sh/uv/), Node.js 22+, git. Optional: the GitHub CLI (`gh`) for branch protection.

```bash
# 1. Create your repo from this template (GitHub "Use this template"), clone it, then:
node scripts/init-project.mjs --name my-app --owner your-github-handle

# 2. Install everything (Python deps, Node deps, git hooks, the E2E Chromium)
uv sync
npm install

# 3. Prove the harness works on your machine
npm run check

# 4. Commit, push, wait for the first CI run, then protect main (as a repo admin)
node scripts/protect-branch.mjs          # team: PRs, a code owner review and all 7 CI checks
node scripts/protect-branch.mjs --solo   # one maintainer: PRs and all 7 CI checks, no approval
```

GitHub doesn't let you approve your own PR, so a solo maintainer needs `--solo`, or `main` can never be merged into.
If you set up a ruleset by hand instead, add **Require status checks to pass** with the 7 CI jobs. Requiring a PR alone doesn't stop a red build from being merged.

## Daily use

```bash
npm run dev       # backend http://127.0.0.1:8000, frontend http://localhost:5173
npm run check     # build → lint → unit → integration → functional → security → architecture
npm run check -- lint unit   # run selected stages only
npm run format    # format everything
npm run metrics   # time-to-validated-outcome report
```

With Claude Code, start a feature with `/spec <what you want>` and follow the stages in `docs/PROCESS.md`.
Other agents read `AGENTS.md` and follow the same documents.
For a worked example of the full loop, see `docs/specs/personalised-greeting.md` and `docs/plans/PLAN_personalised-greeting.md`.

## Layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI, with layers `api/` → `services/` → `domain/` and tests under `tests/unit` and `tests/integration` |
| `frontend/` | React + Vite + TypeScript (strict), with vitest tests next to the code |
| `e2e/` | pytest + Playwright functional tests: outside journeys and inside network-contract checks |
| `docs/` | Rules, product spec, specs and plans, templates, harness log, metrics |
| `.claude/` | Claude Code permissions, guard and format hooks, skills, reviewer subagents |
| `.github/` | CI (one job per stage), PR template, CODEOWNERS, Dependabot |
| `scripts/` | Cross-platform `.mjs` tools: the check runner, secrets scan, metrics, init, branch protection |

## Adapting it

Swap the Hello World app for your own code, but keep the contract: every rule an agent must follow is either **enforced** by a check or **explicitly marked as documented only**.
When the agent gets something wrong, run `/retro` instead of adding more human review.
