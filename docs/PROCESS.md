# Process

## Setup

```bash
uv sync        # Python deps into .venv (npm install needs uv, for Python Playwright)
npm install    # Node deps, git hooks (lefthook) and the E2E Chromium
npm run dev    # backend :8000 + frontend :5173
npm run check  # full verification pipeline
```

## Staged autonomy

Work moves through stages, and each stage leaves an artifact behind. Humans spend attention only at the gates.

| Stage | Who | Artifact | Skill |
|---|---|---|---|
| 1. Specify | Human intent, agent drafts | `docs/specs/<name>.md` | `/spec` |
| 2. Plan | Agent | `docs/plans/PLAN_<name>.md` | `/plan` |
| **Gate: approve plan** | **Human** | Plan reviewed | |
| 3. Implement | Agent | Commits, one per phase | `/implement` |
| 4. Verify | Agent + tools | `npm run check` output, ticked criteria | `/implement` |
| 5. Ship | Agent | Branch and PR description | `/ship` |
| **Gate: approve PR** | **Human** | Review on the "human attention needed" items | |
| 6. Learn | Agent, human confirms | `docs/HARNESS_LOG.md` entry, harness change | `/retro` |

### 1. Specify

- Copy `docs/templates/SPEC_TEMPLATE.md` to `docs/specs/<name>.md`.
- Every field must be filled in. If you can't fill one from the request, ask. Don't guess.

### 2. Plan

- Write `docs/plans/PLAN_<name>.md` from `docs/templates/PLAN_TEMPLATE.md`. **Write no code.**
- Split the work into phases (usually 2–6), each building on the last.
- Give every phase success criteria that can be checked, written as checkboxes: tests passing, command output, API responses, or pages checked in a browser.
- **Stop and wait for approval.**

### 3–4. Implement and verify

Build the phases in order without stopping. For each phase:

1. Build it, with tests.
2. Check every success criterion and fix any failures.
3. Tick the criteria in the plan and update `docs/STATUS.md`.
4. Commit. If the pre-commit hook fails, fix the cause and commit again.

After the last phase, run `npm run check` and report the result.

### 5. Ship

- Work on a branch named `feat/<name>` or `fix/<name>`.
- Run the `code-reviewer` and `security-reviewer` subagents and resolve what they find.
- Fill in `.github/PULL_REQUEST_TEMPLATE.md`. A human opens or merges the PR, because agents never push.

### 6. Learn

- Run `/retro` after every PR, and whenever a defect escapes or a review repeats feedback.

## Verification pipeline

`npm run check` runs these stages in order and stops at the first failure:

```
build → lint → unit → integration → functional → security → architecture
```

| Stage | Tools |
|---|---|
| build | `tsc`, `vite build` |
| lint | ruff format/check, pyright, Prettier, ESLint |
| unit | pytest `backend/tests/unit`, vitest (80% coverage gates), `node --test` on `.claude/hooks/*.test.mjs` and `scripts/*.test.mjs` (the harness's own tests) |
| integration | pytest `backend/tests/integration` |
| functional | pytest + Playwright `e2e/` on a fresh production build: outside (what the user sees) and inside (the exact API calls) |
| security | pip-audit, npm audit, detect-secrets |
| architecture | import-linter |

The pre-commit hook runs the fast stages for staged files. CI runs every stage on every PR.

## Small changes outside a plan

Bug fixes and tweaks that need no design decision can skip stages 1–2, but they still need a test, a passing `npm run check` and a commit.

## Background processes

Stop every dev server you start. On Windows, `uvicorn --reload` leaves a worker process that outlives its parent, so stop it by port, not by its parent's PID.

## Commits

- One logical change per commit. Use the imperative mood ("Add greeting name validation").
- Never amend or rewrite commits that have been shared.
- Everything must work on Windows, macOS and Linux. Write scripts as `uv run` commands or `.mjs` files, never bash-only.
