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

## 2026-10-26: CI publishes screenshots of the UI on every run
- Signal: successful pattern
- What happened: For PR #3, the screenshots reviewers saw were ones an agent took by hand in a dev browser. Some showed the UI before the last phase, and attaching them took several manual attempts. Nothing tied them to the code being merged.
- Improvement: test and CI change, approved in `docs/specs/ci-screenshot-artifacts.md` (D1–D4).
  - `e2e/test_screenshots.py` captures 5 screens × 2 themes × 2 widths against its own servers and fixed sample data. Each capture waits until its screen has loaded, checks its exact API calls, and names the screen when one fails.
  - `.github/workflows/ci.yml` uploads `ui-screenshots` with `if: always()`, kept 14 days with `if-no-files-found: error`. `scripts/screenshot-summary.mjs` writes the job summary and fails on a missing or unexpected file.
  - `scripts/harness-config.test.mjs` checks the workflow steps and the PR template line.

  Proof:
  - dropping a screen failed `test_every_screen_is_captured`
  - holding a request failed the capture with the screen's name and saved no image
  - a folder missing one image made the summary exit 1
  - removing `if: always()` failed the config test
  - two local runs produced identical images

  The stage got 8.4 s slower (159.6 s to 168.0 s).
- Enforced: yes (functional stage, unit stage, and the CI step itself)

## 2026-10-26: The plan's coverage table named tests that didn't exist
- Signal: repeated review feedback
- What happened: The app-shell-and-design-system plan mapped each spec criterion to checks written as "3 vitest" or "2 outside plus inside E2E". At `/ship`, `code-reviewer` found four criteria that no test covered:
  - focus return after Cancel and after success
  - the home header buttons
  - hints on two fields
  - busy state on Search and Clear search

  The table claimed "3 vitest" for some of them, but those tests didn't exist. This repeats the 2026-10-25 entry below, where a plan quietly narrowed the spec's coverage and nothing checked it.
- Improvement: test. `scripts/harness-config.test.mjs` (`planCoverage`) now:
  - fails when a `path::test name` reference in any `docs/plans/PLAN_*.md` matches no test (a Python `def`, or a quoted vitest title)
  - fails when a row of a plan's "Spec coverage" table names no test

  The app-shell plan's table was rewritten to name its tests. Proof: on the old table the check listed the 10 references that didn't resolve, and its unit test catches both a row with no test and a renamed test.

  Approved by the human:
  - `/plan` adds the table with every test named.
  - `docs/templates/PLAN_TEMPLATE.md` carries it.
  - `/implement` brings the names up to date before setting the plan to Done.

  Every row must name a test at all times. The named tests must exist only once the plan is **Done** (`isDone`), because during `/implement` they're still being written.
- Enforced: yes (unit stage, `scripts/harness-config.test.mjs`)

## 2026-10-26: Nothing stopped a `javascript:` link
- Signal: security issue
- What happened: `security-reviewer` found no `javascript:` links, but only because every `href` and `to` happened to be a fixed path. No rule would stop one.
- Improvement: safeguard, approved by the human. `eslint.config.js` `no-restricted-syntax` now bans a `javascript:` URL (any case) in an `href` or `to` attribute, as a string, an expression or a template literal. Proof: a probe file with one of each got 3 errors, and its plain `/groups/1` link none. Deleted.
- Enforced: yes (lint stage)

## 2026-10-26: Third-party origins were only checked on screens a test opened
- Signal: security issue
- What happened: The spec forbids requests to other origins (fonts and icons must be bundled). The only check was the E2E `traffic` fixture, which sees only the screens a test opens. `security-reviewer` suggested enforcing it in source.
- Improvement: safeguard. `frontend/src/origins.test.ts` scans `frontend/index.html`, `frontend/public/` and `frontend/src/**/*.{ts,tsx,css}` (test files excluded) for absolute or protocol-relative URLs. Only the SVG namespace is allowed. Proof: a Google Fonts `<link>` added to `index.html` failed exactly that file's case. Reverted.
- Enforced: yes (unit stage, vitest)

## 2026-10-26: A check would have passed without checking anything
- Signal: successful pattern
- What happened: The raw-colour scan first imported stylesheets with `?raw`. Vitest replaces imported CSS with an empty string, `?raw` included, so the scan saw 0 bytes and would have passed against anything. The plan's negative proof (plant `#ff0000`, expect a failure) caught it. The test now reads files from disk and asserts each one has content. In the same vein, review found two tests whose assertions held without the behaviour: the font-fallback test passed even if no font was requested, and a test named for a link's address checked only the title. Both were fixed to prove their trigger happened.
- Improvement: test, plus a guideline approved by the human. `frontend/src/theme/tokens.test.ts` asserts the scanned files are non-empty. `docs/CODING_GUIDELINES.md` (Tests) now says that a test of an outcome also proves its trigger happened, and that a test scanning files reads them from disk and asserts it found some.
- Enforced: yes for the scans (non-empty assertion); the guideline is documented only (the `code-reviewer` subagent checks it)

## 2026-10-26: Opening a PR took four attempts from the remote prompt
- Signal: repetitive task
- What happened: The human ran the `/ship` hand-over commands with `!` from the remote session.
  - The two-command block didn't run.
  - `gh` wasn't on Git Bash's PATH, though it's installed in `C:\Program Files\GitHub CLI`.
  - The wrapped `gh pr create` line was split, so bash ran the PR body file as a script, which failed harmlessly on its first line.
  - Once `gh` was found, the wrapped title was stored first with a line break and then with three spaces. It took a third `gh pr edit` to fix it.
- Improvement: script. `scripts/open-pr.mjs` (`npm run pr -- <spec-name>`) takes the title from the spec's `# Spec:` heading and the body from `.git/PR_BODY_<name>.md`. It finds `gh` on PATH or where Windows installs it, and refuses names that aren't kebab-case. `scripts/open-pr.test.mjs` checks title extraction, that every spec has a usable title, and the Windows search paths. It's for the human: agents still never open PRs. Approved by the human: `/ship` now hands over `npm run pr -- <name>`, one short command per line. It saves final-UI screenshots to `.playwright-mcp/pr-<name>/`, which the script attaches with `gh pr create --attach` (gh 2.103+). Contrary to what this session first told the human, `gh` can upload images to a PR.
- Enforced: yes for the script's behaviour (unit stage); using it is documented only, in the `/ship` skill

## 2026-10-26: A uvicorn worker kept port 8000 after its parent was stopped
- Signal: harness defect
- What happened: `docs/PROCESS.md` says to stop dev servers by port. Stopping the process that owned :8000 left the port held: Windows still reported the dead parent's PID, while its `multiprocessing` child (the reload worker) kept the socket. The worker had to be found by parent PID and stopped separately.
- Improvement: guideline, approved by the human. `docs/PROCESS.md` (Background processes) now says to stop the whole tree (`taskkill /T /F /PID <pid>`), or the children of the PID that `Get-NetTCPConnection` reports, then confirm the port is free.
- Enforced: documented only (a process-tree kill is environment-specific; the E2E stage already refuses to start on a busy port)

## 2026-10-26: STATUS still said "awaiting review" after the merge
- Signal: harness defect
- What happened: `/implement` set `docs/STATUS.md` to "awaiting `/ship` and review", and nothing updated it after PR #3 merged. `main` claimed work was in progress that had shipped.
- Improvement: fixed in this retro. Approved by the human: `/retro` now has a step to move merged work out of STATUS's "In progress".
- Enforced: documented only (a check can't know when a PR merged without network access)

## 2026-10-26: A plan named a dependency version from memory
- Signal: harness defect
- What happened: The plan said `react-router` 7.x. `npm install` brought 8.5.0, the current release, which needs Node 22.22+. The API used was unchanged and `.nvmrc` (24) was fine, but the plan had to be corrected during implementation.
- Improvement: guideline, approved by the human. The `/plan` skill now checks a new dependency's current version and requirements (`npm view <pkg> version engines peerDependencies`, `uv pip index versions <pkg>`) before naming it.
- Enforced: documented only

## 2026-10-26: The guard stopped an unnecessary suppression comment
- Signal: successful pattern
- What happened: While writing `ui/Button.tsx`, an `eslint-disable-next-line` for a rule from a plugin this repo doesn't use was blocked by the guard hook before the file was written. The comment was simply removed.
- Improvement: none needed. The safeguard worked as designed.
- Enforced: yes (guard hook)

## 2026-10-25: Outside journeys shipped without inside tests
- Signal: escaped defect
- What happened: The members-and-groups spec says every journey gets an outside and an inside E2E test. The plan's phase 5 list quietly narrowed that, and implementation followed the plan. `code-reviewer` found four outside journeys with no inside test (taken user ID, reject, unknown group name, taken group name); they were added before the PR. Nothing checked the pairing. When this retro added the check, it found a fifth gap: the display-name markup journey had no inside test proving the browser sends no request.
- Improvement: test. Inside tests now carry `@covers("<journey>")` (a no-op decorator in `e2e/network.py`). `scripts/harness-config.test.mjs` fails when a `test_journeys.py` journey has no `@covers`, or when a `@covers` name matches no journey. The fifth gap is closed by `test_markup_display_name_is_refused_before_any_request`. Proof: with the decorators missing, the check listed all 12 journeys. With one journey uncovered, it named exactly that one.
- Enforced: yes (unit stage, `scripts/harness-config.test.mjs`)

## 2026-10-25: Invisible characters reached source through tool-input escapes
- Signal: security issue
- What happened: Test cases for zero-width and direction-override characters were written into `backend/tests/integration/*.py` as the raw invisible characters, not escapes. The agent noticed and fixed it before commit. The cause is that tool input is JSON, so a `\u` escape typed there is decoded into the character before any file or shell sees it. The new check caught the same thing again in its own test file during this retro. Raw format characters make code read differently from how it runs (Trojan Source).
- Improvement: safeguard. `scripts/harness-config.test.mjs` scans every tracked source file (`git ls-files`) for Unicode category Cf and reports file, line and code point. Proof: a planted U+202E in `backend/domain/models.py` failed the check; removing it made it pass. `docs/CODING_GUIDELINES.md` General item 6 says to write doubled backslashes in tool input.
- Enforced: yes (unit stage)

## 2026-10-25: Shell writes skip the guard's content checks
- Signal: harness defect
- What happened: The guard checks the content of Write and Edit calls (suppression comments, coverage thresholds, `pyproject.toml` rule exclusions), but not shell commands that write files. In members-and-groups:
  - the import-linter contracts in `pyproject.toml`, including `allow_indirect_imports = true`, were edited through Python scripts in Bash with no prompt;
  - a `# type: ignore` was written to a test file the same way, and was caught only by the agent;
  - one script opened `pyproject.toml` for writing before reading it and emptied it, which caused a backend-wide reformat that had to be reverted;
  - a multi-command shell script that failed to parse still ran its first commands, which duplicated a class.

  A probe confirmed that the current guard returns no decision for `sed -i 's/fail_under = 80/fail_under = 0/' pyproject.toml`.
- Improvement: safeguard, approved by the human. `.claude/hooks/guard.mjs` now asks when a shell command writes (redirect, `tee`, `sed -i`, `open(..., "w")`, `write_text`, `writeFileSync`, `Set-Content`, `Out-File`) and either contains a suppression comment or names `pyproject.toml`, `package.json` or `vite.config.ts`. `.claude/hooks/guard.test.mjs` has 8 new cases. Proof: before the change, the 4 "ask" cases failed with no decision; after it, all 54 guard tests pass and reads, searches and `uv add` stay silent. `docs/CODING_GUIDELINES.md` General item 6: edit files with Edit and Write, not scripts.
- Enforced: yes (guard hook, tested in the unit stage)

## 2026-10-25: STATUS claimed branch protection the plan can't provide
- Signal: harness defect
- What happened: `docs/STATUS.md` said `main` was protected by `scripts/protect-branch.mjs --solo`, and `docs/RULES.md` lists branch protection as what enforces "never commit straight to `main`". The repo is private on a free plan, and the protection API returns 403 ("Upgrade to GitHub Pro or make this repository public"). Earlier attempts to apply protection failed on gh not being on PATH, which hid this.
- Improvement: safeguard, approved by the human. `scripts/refuse-main.mjs` runs as a lefthook pre-commit job and refuses commits on `main` once a remote exists. `docs/RULES.md` names it as the enforcement, with GitHub branch protection added once the repo is public or on GitHub Pro. `docs/STATUS.md` is corrected. Proof: `scripts/refuse-main.test.mjs` failed until `lefthook.yml` ran the check, and the script exits 1 on `main` and 0 on a feature branch.
- Enforced: yes (lefthook pre-commit; a local hook, so CI and review remain the backstop for merges)

## 2026-10-25: Patterns that made members-and-groups tests deterministic
- Signal: successful pattern
- What happened: three test techniques held up locally and on CI with no flakes:
  - multi-step inside tests took `before = len(traffic.api_calls())` and asserted only the calls caused by the action under test;
  - session expiry was tested by overriding a clock dependency (`app.dependency_overrides[get_clock]`), with no sleeps;
  - the double-approval race was tested with two threads behind a `threading.Barrier`, which `BEGIN IMMEDIATE` transactions resolve to exactly one 200 and one 404.
- Improvement: guideline, approved by the human: `docs/CODING_GUIDELINES.md` Tests (the `before` slice, clock overrides, `threading.Barrier` races). `docs/PROCESS.md` also notes that MCP browser checks against `npm run dev` must open `http://localhost:5173`, because Vite listens on `localhost` (`::1`) and `127.0.0.1:5173` refused the connection.
- Enforced: documented only (patterns, not rules)

## 2026-10-25: Security review of members-and-groups found low-severity gaps
- Signal: security issue
- What happened: `security-reviewer` found nothing blocking on `feat/members-and-groups`, but six low-severity issues for a local, trusted app whose passwords aren't checked yet (spec D1):
  1. An owner sees only a display name on a pending request, and display names aren't unique, so an impostor can be approved.
  2. Member lists returned co-members' user IDs, and under D1 a user ID is enough to sign in.
  3. Storage failures logged SQL bound values (names, descriptions) through the chained `DBAPIError`.
  4. Zero-width, direction-override and C1 characters were accepted in names and descriptions, allowing look-alike group names.
  5. `SameSite=Strict` doesn't stop form posts from other `localhost` ports, and the bodiless POST routes (join by ID, approve, reject, sign-out) accept them.
  6. Every sign-in adds a session row, and expired rows are only removed when presented, so the table grows without limit.
- Improvement: safeguard, for findings 2–4 in the same branch:
  - members are returned by display name only (`MemberNameResponse`)
  - `create_engine(..., hide_parameters=True)`, tested by `test_storage_errors_never_carry_the_bound_values`
  - every free-text field refuses Unicode categories Cf and Cc, with integration cases for U+200D, U+FEFF, U+202E and U+0085

  Findings 1, 5 and 6 are deferred to the real-authentication spec. Proposed safeguards: unique, normalised display names, or a stable identifier on each pending request (1); an `Origin`/`Sec-Fetch-Site` check on unsafe methods, with a test that walks `app.routes` and sends a cross-origin form post to every POST (5); purging expired sessions at sign-in and capping live sessions per member (6).
- Enforced: yes for 2–4 (integration and unit tests). Documented only for 1, 5 and 6 (out of scope until passwords are checked).

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
