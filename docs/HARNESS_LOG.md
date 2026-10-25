# Harness Log

The flywheel record. Every failure, repeated piece of feedback or successful pattern becomes a harness improvement here.
Add entries with `/retro`, newest first.

Entry format:

```
## YYYY-MM-DD: <short title>
- Signal: escaped defect | architecture violation | security issue | repeated review feedback | repetitive task | successful pattern | harness defect
- What happened: <facts>
- Improvement: <test | rule | safeguard | guideline | skill | template>, with the file(s) changed
- Enforced: yes (<check that now catches it>) | documented only (<why it can't be enforced>)
```

## 2026-10-25: Branch protection locked out a solo maintainer
- Signal: harness defect
- What happened: PR #6 (python-e2e-whitebox) couldn't be merged. The human's ruleset required 1 approval, and GitHub doesn't let you approve your own PR. `scripts/protect-branch.mjs` would have done the same: it required a code owner review and applied it to admins too. The human set approvals to 0, but the ruleset still had no required status checks, so a red PR could have been merged.
- Improvement: test. `protect-branch.mjs --solo` still requires PRs and all 7 CI checks, but no approval. Its rules come from an exported `protection()`, which `scripts/protect-branch.test.mjs` tests, along with a check that the required checks match the CI job names. The README and `init-project.mjs` explain when to use `--solo`, and that a hand-made ruleset needs required status checks.
- Enforced: yes (the unit stage tests both modes and the check names)

## 2026-10-25: Rule exclusions in pyproject.toml aren't guarded
- Signal: security issue
- What happened: Implementing python-e2e-whitebox needed a ruff per-file ignore for S603. The guard correctly blocked the `# noqa` comments, and the human approved the ignore. But the guard never asked about the `pyproject.toml` edit that added it: `pyproject.toml` isn't a protected file, and the guard only checks its coverage thresholds. An agent could disable any ruff rule there without a prompt. Both reviewers flagged it.
- Improvement: safeguard (approved by the human). The guard asks before an edit to `pyproject.toml` adds any of these:
  - `per-file-ignores` or a per-file rule list
  - `ignore`, `extend-ignore`, `exclude` or `extend-exclude`
  - a pyright `report*` turned off, or a `typeCheckingMode` change

  `eslint.config.js` was already protected. Run against the previous guard, the 6 new "ask" cases fail, and the 3 harmless edits pass either way.
- Enforced: yes (guard tests in the unit stage and pre-commit)

## 2026-10-25: Pre-commit didn't lint the new E2E Python
- Signal: harness defect
- What happened: python-e2e-whitebox added `e2e/` to pyright's `include`, but lefthook's `python` job still matched only `backend/**/*.py`. So ruff and pyright never ran on `e2e/*.py` at commit time, and only CI would catch them. The code reviewer found it, and it was fixed in the PR.
- Improvement: test. `scripts/harness-config.test.mjs` fails if any folder pyright checks is missing from lefthook's `python` glob. Run against the feature's Phase 1 files, it fails with "Add these to lefthook.yml's python glob: e2e".
- Enforced: yes (the unit stage)

## 2026-10-25: networkidle gave misleading "no extra calls" evidence
- Signal: harness defect
- What happened: The first inside tests waited with `wait_for_load_state("networkidle")`, which settles once per navigation. The code reviewer's probe showed that a call made after a click arrived after the assertion, so "no unexpected extra calls" held only by timing. It was fixed in the PR: tests now wait for the expected response with `page.expect_response`.
- Improvement: test. `scripts/harness-config.test.mjs` fails if an `e2e/test_*.py` file uses `networkidle`, `wait_for_timeout` or `time.sleep`. Run against the Phase 2 tests, it lists both `networkidle` lines. The rule is in `docs/CODING_GUIDELINES.md`.
- Enforced: yes (the unit stage)

## 2026-10-25: Traffic recorder crashed on redirects and unreadable bodies
- Signal: harness defect
- What happened: `e2e/network.py` read every response body. A redirect (the reviewer's trailing-slash probe) or a body Playwright had already dropped (a stubbed 500) raised an exception. So the test crashed instead of listing the calls it saw, which broke a spec failure condition. It was fixed in the PR: bodies are read only for API calls that aren't redirects, and unreadable bodies are recorded as unavailable.
- Improvement: test (partial). `test_backend_failure_requests_greeting_once` exercises the unreadable-body path in every run. The redirect path was checked with a scratch probe, recorded in PR #6.
- Enforced: partly (the redirect case has no committed test: a redirecting route sends the browser to the backend's own port, which the foreign-origin check rightly fails)

## 2026-10-25: Outside tests acted before the initial load settled
- Signal: repeated review feedback
- What happened: Two outside journeys filled the name field before the default greeting had loaded. If the initial response arrived last, it could overwrite the greeting or the alert, and the test would flake. The TypeScript suite had the same race, so it was carried over. It was fixed in the PR.
- Improvement: guideline. `docs/CODING_GUIDELINES.md` says to wait for the page's initial state before interacting.
- Enforced: documented only (can't tell from the source alone whether a test waited for the right state; review checks it)

## 2026-10-25: Metrics counted the Status move at done as spec rework
- Signal: harness defect
- What happened: `npm run metrics` reported spec rework 1 for python-e2e-whitebox. The only spec change after approval was ticking the acceptance criteria and moving `Status:` to **Done** in the same commit, and the checkbox-only rule didn't allow the Status line.
- Improvement: test. `isProgressOnly` (renamed from `isCheckboxOnly`) ignores `Status:` lines too, covered by a test built from that commit's diff. The feature now reports 0.
- Enforced: yes (the metrics tests in the unit stage)

## 2026-10-25: Negative proofs gave the strongest evidence
- Signal: successful pattern
- What happened: The most convincing checks in this feature broke something on purpose:
  - With the greeting fetched twice, all 5 inside tests failed and all 4 outside tests passed.
  - Running the PowerShell guard test against the old settings made it fail.
  - Requests to a foreign origin and a busy port were each shown to fail the session.

  Each one showed that a check catches the problem it's meant to catch, not just that it passes.
- Improvement: template. `docs/templates/PLAN_TEMPLATE.md` asks for a negative proof as a success criterion for any new check or safeguard.
- Enforced: documented only (a plan reviewer checks for it)

## 2026-10-25: Guard and deny rules didn't cover the PowerShell tool
- Signal: security issue
- What happened: The retro on harness creation found that `.claude/settings.json` only sent `Bash|Read|Edit|Write|MultiEdit` calls through the guard hook, and its deny rules only listed `Bash(...)` patterns. On Windows, Claude Code also has a PowerShell tool, so `git push`, `--no-verify` or reading `.env` through PowerShell bypassed every agent safeguard. No bypass happened; the gap was in the config.
- Improvement: safeguard. The hook matcher and deny rules now include PowerShell. `guard.mjs` applies its shell rules to every tool in `SHELL_TOOLS`, and also catches `$env:LEFTHOOK` and the PowerShell cmdlets that write to harness files. A test fails if any shell tool in `SHELL_TOOLS` isn't sent through the guard or lacks a push deny rule. Run against the old settings, it fails with "PowerShell is not routed through the guard".
- Enforced: yes (guard tests in the unit stage and pre-commit; a live PowerShell call containing `git push` is now denied)

## 2026-10-25: Unit stage passed on Windows but failed on Linux CI
- Signal: harness defect
- What happened: The first CI run on GitHub failed the unit job. `node --test .claude/hooks/ scripts/` passed on Windows, but on Linux Node tried to load each directory as a module (`Cannot find module …/.claude/hooks`). The pre-commit hook also ran only the guard tests, never `scripts/metrics.test.mjs`. CI also warned that `checkout@v4`, `setup-node@v4` and `setup-uv@v6` run on deprecated Node 20, and Dependabot opened a TypeScript 7 PR against the documented `~6.0` pin.
- Improvement: safeguard. `package.json` and `lefthook.yml` pass explicit `*.test.mjs` globs, which Node expands the same way on every OS, and the hook also runs on `scripts/` changes. The actions moved to Node 24 versions (`checkout@v7`, `setup-node@v7`, `upload-artifact@v7`, `setup-uv@v10.2.0`), and `.github/dependabot.yml` ignores TypeScript majors until the pin is lifted.
- Enforced: yes (CI runs every stage on Linux, so a check that only passes on Windows now fails the PR)

## 2026-10-25: Mis-cased working directory broke vitest on Windows
- Signal: harness defect
- What happened: `npm run check` in a fresh clone failed with "Invalid Chai property: toBeInTheDocument". The shell path was `C--Data…` while the folder on disk is `c--Data…`. Windows ignores the difference, but Vite loaded `vitest` twice, so jest-dom extended the wrong `expect`.
- Improvement: safeguard. `scripts/check.mjs` compares the working directory with its real path and stops with an explanation.
- Enforced: yes (`npm run check` exits with 2 and names both paths)

## 2026-10-25: Metrics counted ticked checkboxes as spec rework
- Signal: harness defect
- What happened: After the personalised-greeting plan was approved, the only change to its spec was ticking the acceptance criteria at done. `npm run metrics` still reported spec rework 1.
- Improvement: test. `scripts/metrics.mjs` now ignores checkbox-only diffs (`isCheckboxOnly`), covered by `scripts/metrics.test.mjs`.
- Enforced: yes (the metrics tests run in the unit stage)

## 2026-10-25: E2E verified a stale dev server
- Signal: harness defect
- What happened: Playwright's `reuseExistingServer` reused a `uvicorn --reload` worker left on :8000 by an earlier manual run. On Windows, the reload worker outlives its parent. The new E2E tests failed against the old code. With different code they could have passed while testing the wrong build.
- Improvement: safeguard. `playwright.config.ts` uses dedicated ports (8100/5273) and never reuses a server, and the Vite proxy target comes from `API_PORT`. Two new test rules were added to `docs/CODING_GUIDELINES.md`.
- Enforced: yes (the functional stage always starts its own servers, and fails if a port is already taken)

## 2026-10-24: A second `npm run check` run failed on the import-linter cache
- Signal: harness defect
- What happened: The architecture stage writes `.import_linter_cache/`, and on the next run Prettier's check flagged those files.
- Improvement: safeguard. Added `.import_linter_cache/` to `.gitignore`, which Prettier respects.
- Enforced: yes (repeat runs of `npm run check` are clean)

## 2026-10-24: A test relied on FastAPI internals
- Signal: successful pattern
- What happened: A unit test read `app.routes`, which broke because FastAPI now includes routers lazily. Asserting on the public OpenAPI schema worked, and it is stable across versions.
- Improvement: guideline. `docs/CODING_GUIDELINES.md` now says to assert through public interfaces.
- Enforced: documented only (the code-reviewer subagent checks it)

## 2026-10-24: The guard blocked a harmless command that mentioned `.env`
- Signal: harness defect
- What happened: The guard denied a shell command that wrote `.env.example`, because its comment text contained `.env`.
- Improvement: none, by choice. Conservative matching on secrets is intended. The file tool can write `.env.example`, and the guard allows that.
- Enforced: documented only (accepted false positive)
