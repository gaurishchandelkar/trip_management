# AGENTS.md

This file is the entry point for any coding agent (Claude Code, Copilot, Cursor, Codex, ...).
It's the same for every tool. Tool-specific files such as `CLAUDE.md` only add to it.

## What this repo is

A Hello World React + FastAPI app inside an **Agentic Harness**:

- **Rules guide**: the documents in `docs/` tell you how to work.
- **Safeguards protect**: hooks, linters and permission rules block unsafe changes.
- **Verification gives evidence**: `npm run check` shows that a change works.

Your goal is to **maximize useful autonomy within well-defined, verifiable boundaries**.

## Roles

| Humans own | Agents own |
|---|---|
| Intent, architecture, trade-offs, risk, approval | Planning, implementation, testing, iteration, documentation |

## Read before any change (in this order)

1. `docs/RULES.md`: the operating rules and hard lines
2. `docs/CODING_GUIDELINES.md`: coding standards, patterns and quality expectations
3. `docs/PROCESS.md`: the staged workflow from spec to PR
4. `docs/SECURITY_GUIDELINES.md`: security boundaries
5. `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/STATUS.md`: what the product is now and how it's built

## Repo map

| Path | Contents |
|---|---|
| `backend/` | FastAPI app, layered `api/` → `services/` → `domain/` |
| `frontend/` | React + Vite + TypeScript (strict) |
| `e2e/` | pytest + Playwright functional tests: outside journeys and inside network-contract checks |
| `docs/` | Rules, product docs, `specs/`, `plans/`, `templates/`, `HARNESS_LOG.md`, `METRICS.md` |
| `.claude/` | Claude Code settings, hooks, skills and subagents |
| `scripts/` | Cross-platform `.mjs` helpers |

## Commands

| Command | Purpose |
|---|---|
| `uv sync && npm install` | Install everything, including the git hooks |
| `npm run dev` | Run backend (:8000) and frontend (:5173) |
| `npm run check` | Full verification pipeline. Must pass before handing over work |
| `npm run format` | Format all code |

## Hard lines

- Never push, and never skip or bypass git hooks.
- Never lower a threshold, disable a rule or exclude a file to get a passing run. Stop and ask instead.
- Never read, write or print `.env*` files or secrets.
- Never implement before the plan is approved (see `docs/PROCESS.md`).
