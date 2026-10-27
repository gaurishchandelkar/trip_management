# Caravan

**Plan trips together.** Caravan is a trip planning app for groups of friends. Members register, sign in and organise themselves into groups: anyone can start a group for their next trip, and friends ask to join. Each group's owner decides who's in.

It's a React + FastAPI app with SQLite storage, built by AI agents inside an [Agentic Harness](#how-its-built): every change goes from spec to plan to tested code, with a human approving each stage.

> **Local and trusted use only.** Sign-in asks for a password but doesn't check it yet, so anyone who knows a user ID can sign in as that member. Real passwords come in a later spec. Don't expose the app beyond your own machine or network.

## What you can do

- **Register and sign in** with a user ID and a display name. Sessions last 7 days.
- **Start a group** for a trip, with a name and an optional description. You become its owner and first member.
- **Browse and search groups**, and ask to join one from the list or by typing its exact name.
- **Approve or reject requests** as a group's owner. Members see who else is in the group; non-members see only its name, description, owner and size.
- **Share a link** to any group: each one has its own address (`/groups/{id}`), and refresh and Back work.

The interface follows the system's light or dark theme, works on phones down to 360 px wide, and meets WCAG AA contrast. Trips themselves (itineraries, expenses) aren't built yet. See [Roadmap](#roadmap).

The full behaviour, limits and API are in [`docs/SPEC.md`](docs/SPEC.md).

## Screenshots

Every CI run captures the main screens (sign-in, home, the New group dialog, a group and Page not found) in light and dark at 360 and 1280 px. To see them, open a run under the repo's **Actions** tab and download its `ui-screenshots` artifact. Artifacts are kept 14 days.

## Run it locally

You need [uv](https://docs.astral.sh/uv/), Node.js 22.22 or later (`.nvmrc` pins 24) and git. Python 3.12 is installed by uv.

```bash
uv sync           # Python dependencies
npm install       # Node dependencies, git hooks and the Chromium the E2E tests use
npm run dev       # backend http://127.0.0.1:8000, frontend http://localhost:5173
```

Open http://localhost:5173, register a member, and start a group. To try joining and approving, register a second member in a private window.

Data lives in `trip.db` in the repo root (git-ignored). Set `TRIP_DB_PATH` to use another file. Delete the file for a fresh start: there are no migrations yet, so a schema change needs a fresh database.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Runs the backend and frontend with reload |
| `npm run check` | The full verification pipeline: build → lint → unit → integration → functional → security → architecture |
| `npm run check -- lint unit` | Runs only the stages named |
| `npm run format` | Formats all Python and TypeScript |
| `npm run metrics` | Reports time to validated outcome, first-pass rate and rework |
| `npm run pr -- <name>` | Opens the PR for a finished spec or a small change, with its title and description. A UI change also gets the 20 e2e screenshots |

## Tech stack

| Area | Choice |
|---|---|
| Frontend | React 19, Vite, TypeScript (strict), React Router 8, plain-CSS design tokens with light and dark themes, a self-hosted Inter font |
| Backend | Python 3.12, FastAPI, Pydantic, in layers: `api/` → `services/` → `storage/` → `domain/` |
| Storage | SQLite through SQLAlchemy 2.x |
| Tests | pytest and vitest with 80% coverage gates; pytest + Playwright end-to-end tests against a production build |
| CI | GitHub Actions, one job per stage, plus Dependabot |

Why each piece was chosen, and what was ruled out, is in [`docs/TECH_STACK.md`](docs/TECH_STACK.md).

## Layout

| Path | Contents |
|---|---|
| `frontend/` | The React app: screens in `src/`, design tokens in `src/theme/`, components in `src/ui/`, with vitest tests next to the code |
| `backend/` | The FastAPI app, with tests in `tests/unit` and `tests/integration` |
| `e2e/` | End-to-end tests: journeys that check what a member sees, network-contract tests that check the exact API calls behind each one, and the screenshot captures |
| `docs/` | Product spec, feature specs and plans, rules and guidelines, harness log, metrics |
| `.claude/`, `.github/`, `scripts/` | The agent harness, CI and cross-platform tooling |

## How it's built

Caravan is developed by coding agents inside the Agentic Harness from [AI Agents in the Fast Lane: Engineering for Hyper Productivity](https://medium.com/@gaurish-chandelkar/ai-agents-in-the-fast-lane-engineering-for-hyper-productivity-fcbcd902ee9a). Agents plan, implement and test; humans own intent, architecture and approval.

- **Staged work:** `/spec` → `/plan` → *a human approves* → `/implement` → `/ship` → *a human merges* → `/retro`. Each feature's spec and plan are in [`docs/specs/`](docs/specs/) and [`docs/plans/`](docs/plans/), and the stages are in [`docs/PROCESS.md`](docs/PROCESS.md).
- **Safeguards:** strict linting and type checks, layer contracts, dependency and secrets scans, git hooks, and a guard hook that blocks agents from pushing, skipping hooks or reading secrets.
- **Evidence:** `npm run check` runs the same seven stages locally and in CI, and must pass before any hand-over.
- **Flywheel:** after each PR, `/retro` turns failures and review findings into new tests, rules or safeguards, recorded in [`docs/HARNESS_LOG.md`](docs/HARNESS_LOG.md).

Any coding agent starts at [`AGENTS.md`](AGENTS.md). Claude Code also reads [`CLAUDE.md`](CLAUDE.md).

## Roadmap

| Status | Feature |
|---|---|
| Done | Members, sign-in and groups with owner approval ([spec](docs/specs/members-and-groups.md)) |
| Done | The Caravan app shell and design system: addresses, dialogs, light and dark themes ([spec](docs/specs/app-shell-and-design-system.md)) |
| Done | Screenshots of every screen on each CI run ([spec](docs/specs/ci-screenshot-artifacts.md)) |
| Not built yet | Trips inside a group: itinerary and shared expenses |
| Not built yet | Real passwords, invitations, leaving and removing members, editing and deleting groups |

What's in progress and the known gaps are in [`docs/STATUS.md`](docs/STATUS.md).
