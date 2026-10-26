# Plan: CI screenshot artifacts

Spec: `docs/specs/ci-screenshot-artifacts.md`
Status: **Done** <!-- Awaiting approval | Approved | In progress | Done -->
Approved: 2026-10-26 by the repo owner, in conversation.

## Approach

A new E2E module, `e2e/test_screenshots.py`, runs inside the existing functional stage (D1). It captures the 20 images into `test-results/screenshots/`. That path is git-ignored, and pytest-playwright clears it at the start of every session, so stale images never survive a run.

The captures use their own backend and preview server, on dedicated ports 8101 and 5274, with a fresh database. The shared E2E database fills with dozens of randomly named groups during a run, and Browse would show them, which breaks the spec's "fixed sample data" criterion. The second pair reuses the session's production build, so there's no second build.

A session-scoped fixture seeds the sample data through the API with Playwright's request context: Ada, Bob, Goa Getaway, Ladakh Road Trip, and Bob's pending request. It hands Ada's signed-in storage state to the capture contexts.

There is one capture test per theme and width, so four in all. Each opens its own browser context with that viewport, colour scheme and reduced motion, then loads each of the five screens. For each screen it:
- waits for the screen's own API responses
- checks the loaded state
- asserts the exact `/api/` calls and no third-party origins
- takes a full-page screenshot with animations disabled and the caret hidden

`scripts/screenshot-summary.mjs` checks the folder against the 20 expected names and prints the "UI screenshots" job summary. It exits non-zero on a missing or extra file. In CI, the functional job adds two `if: always()` steps: upload `ui-screenshots`, kept 14 days with `if-no-files-found: error`, and write the summary.

**Main trade-off:** a second backend and preview server add a few seconds of startup and two more ports. In exchange, the screenshots show the same data on every run, rather than whatever the other E2E tests happened to create.

## Human attention needed

- **Protected files change** (code-owner review):
  - `.github/workflows/ci.yml`: two steps in the `functional` job. The permissions stay `contents: read`, and no new job or required check is added.
  - `.github/PULL_REQUEST_TEMPLATE.md`: one line in the verification section.
  - `docs/PROCESS.md`: the verification pipeline says where the screenshots go.
- **E2E harness change** (`e2e/conftest.py`):
  - The frontend build becomes its own session fixture (`frontend_dist`), shared by `servers` and the new `screenshot_servers`.
  - `_start` lets a caller set `API_PORT`. Today it always forces 8100, so the second preview server can't point at the second backend.

  Existing tests see the same servers on the same ports.
- **Two more dedicated ports:** 8101 (backend) and 5274 (preview). Like 8100 and 5273, the run fails if either is already taken. It never reuses a running server.
- **No new dependencies.** It uses pytest-playwright 0.10.0 and Playwright 1.64.1 (both installed), `actions/upload-artifact@v7` (already in `ci.yml`), and Node built-ins for the summary script.
- **Not journeys:** the capture tests live outside `test_journeys.py`, so they need no `@covers` pair. They do follow the E2E rules: `page.expect_response` waits and no sleeps (the `badWaits` scan covers every `e2e/test_*.py`). The autouse `traffic` fixture still creates its usual page for each test, unused here; each capture context records its own traffic.
- **The final CI criteria need your push.** The upload, the 14-day retention and the job summary can only be seen on a real Actions run. Phase 3 lists them as checked on the PR's CI run, through `gh run view`, after you push the branch.
- **Determinism is checked locally only:** two local runs must produce byte-identical images. The Linux CI runner may render fonts slightly differently from Windows, and nothing compares across machines (baselines are out of scope).
- **The summary step fails the job when the set isn't exactly 20.** Together with `if-no-files-found: error`, missing evidence always shows as a red step, as the spec's failure conditions ask.

## Phase 1: Isolated servers and the captures

- `e2e/conftest.py`:
  - Move the build into a session fixture, `frontend_dist`. `servers` uses it, with no change in behaviour.
  - `_start` merges the caller's env after its defaults, so a caller's `API_PORT` wins.
  - Add a session fixture `screenshot_servers`: backend on 8101 with its own `trip.db`, preview on 5274 with `API_PORT=8101`, both from `frontend_dist`. It only starts when a test asks for it.
- `e2e/test_screenshots.py`:
  - **Constants:** `SCREENS = ("sign-in", "home", "new-group-dialog", "group", "not-found")`, `THEMES = ("light", "dark")`, `WIDTHS = (360, 1280)`, and `OUT = Path("test-results/screenshots")`.
  - **`showcase` fixture** (session scope): seeds the data through `playwright.request.new_context(base_url=...)`:
    - registers `ada` ("Ada Lovelace") and `bob` ("Bob Marley")
    - Bob creates "Ladakh Road Trip"
    - Ada creates "Goa Getaway" ("Beach week in December.")
    - Bob asks to join Goa Getaway

    It returns Ada's `storage_state()` and the Goa Getaway group ID.
  - **`CAPTURES`:** maps each screen name to a function that loads that screen in a given page and returns once it's ready. Each one:
    - waits for the screen's responses
    - expects its heading
    - expects `.skeleton` to have count 0
    - awaits `document.fonts.ready`
  - **`test_captures_every_screen[theme-width]`** (four cases). For each case:
    1. Open a signed-out context and a signed-in context with `viewport`, `color_scheme` and `reduced_motion="reduce"`.
    2. For each screen in `SCREENS`, run its capture, then assert the exact `/api/` call signatures since the previous screen:

       | Screen | Calls |
       |---|---|
       | `sign-in` | `[ME]` (401) |
       | `home` | `[ME, MY_GROUPS, BROWSE]` |
       | `new-group-dialog` | `[]` |
       | `group` | `[ME, GET /api/groups/{id}]` |
       | `not-found` | `[ME]` |

       Also assert no foreign origins.
    3. Assert the body background is the theme's `--color-bg`, and the fixed names are visible.
    4. Write `OUT/<screen>-<theme>-<width>.png` with `full_page=True`, `animations="disabled"` and `caret="hide"`, and assert the file is non-empty.
  - **`test_every_screen_is_captured`:** asserts `CAPTURES` has exactly the spec's five screens, written out literally in the test.

Notes from implementation:
- **Fixture name:** the second server pair's fixture is `screenshot_base_url`, not `screenshot_servers`, because it returns the preview's URL.
- **A fresh page per screen:** each capture loads its screen from scratch, so none depends on the one before it. The dialog capture therefore loads Home first, and its calls are `[ME, MY_GROUPS, BROWSE]`, not `[]`.
- **The dialog's backdrop:** a modal's backdrop covers the viewport, not the page, so the first full-page dialog image at 360 px left the bottom of the page undimmed. The capture now grows the viewport to the page's full height before opening the dialog.
- **Loading check:** the capture checks that the visible text "Loading…" is gone, rather than looking for the `.skeleton` class.
- **A capture that never loads fails, naming its screen.** This covers a failed expectation or a Playwright timeout, not just an `AssertionError`.
- **The second negative proof** held `GET /api/me/groups` in the capture context, with no other code change. The home capture fails naming its screen, and no home image is saved.

Success criteria:
- [x] `uv run pytest e2e/test_screenshots.py --browser chromium --output test-results`: 5 passed. `test-results/screenshots/` holds exactly the 20 expected non-empty PNGs
- [x] Negative proof: dropping `not-found` from `SCREENS` and `CAPTURES` fails `test_every_screen_is_captured` with "Extra items in the right set: 'not-found'", while the 4 capture tests pass. Reverted
- [x] Negative proof: holding `GET /api/me/groups` fails the capture with "home (light, 1280 px) didn't load". Only `sign-in-light-1280.png` was written, with no half-loaded home image. Reverted
- [x] Determinism: two runs produced identical SHA-256 hashes for all 20 files
- [x] The full existing E2E suite passes unchanged (66 passed). `git diff main -- e2e/test_journeys.py e2e/test_network_contract.py` is empty
- [x] `npm run check -- functional`: **159.6 s** on `main`, **168.0 s** with the screenshots, so **+8.4 s** against the 30 s budget
- [x] `du -sh test-results/screenshots`: **1016 KB**, against the 5 MB budget
- [x] Opened the images: each shows its screen, theme and width, with the fixed data (Ada Lovelace, Goa Getaway, Ladakh Road Trip, Bob Marley's pending request)
- [x] `git status --porcelain` after the run shows only this change's files. `test-results/` is git-ignored
- [x] `npm run check -- lint unit integration` passes

## Phase 2: The summary script

- `scripts/screenshot-summary.mjs <dir>`:
  - compares the folder with the 20 expected names (built from the same five screens, two themes and two widths)
  - prints a "UI screenshots" Markdown section: one row per screen, a column for each theme and width, each cell marked present or missing, and a line saying the images are in this run's `ui-screenshots` artifact
  - exits 1 if any file is missing or unexpected
- `scripts/screenshot-summary.test.mjs`: the full set passes; a missing file fails and names it; an extra file fails; and the script's screen list matches `SCREENS` in `e2e/test_screenshots.py`, so the two lists can't drift.

Notes from implementation:
- pytest-playwright clears `test-results/` at the start of **every** pytest session, including the backend unit and integration runs, so a later unit run empties the screenshots folder. That doesn't matter for CI, where the functional job runs only the functional stage, or for `npm run check`, where functional runs after the other pytest stages. It showed up here as a real "0 of 20, exit 1" run of the summary.

Success criteria:
- [x] `node --test scripts/screenshot-summary.test.mjs`: 5 passed
- [x] Negative proof: on a copy of the folder without `group-dark-360.png`, the script exits 1. It reports "19 of 20", marks that cell **missing**, and names the file on stderr
- [x] Negative proof: adding `"join-dialog"` to `SCREENS` in `e2e/test_screenshots.py` fails only `lists the same screens as the capture tests`. Reverted
- [x] `node scripts/screenshot-summary.mjs test-results/screenshots` on fresh captures exits 0 and prints "20 of 20" with every cell present
- [x] `npm run check -- lint unit` passes

## Phase 3: CI wiring and docs

- `.github/workflows/ci.yml`, `functional` job, after the existing steps:
  - `actions/upload-artifact@v7` with `if: always()`, `name: ui-screenshots`, `path: test-results/screenshots/`, `retention-days: 14` and `if-no-files-found: error`
  - `if: always()`, `run: node scripts/screenshot-summary.mjs test-results/screenshots >> "$GITHUB_STEP_SUMMARY"`
- `scripts/harness-config.test.mjs`:
  - a test that the `functional` job has both steps with exactly those settings, and that the workflow's permissions are still only `contents: read`
  - a test that the PR template's verification section mentions `ui-screenshots`
- `.github/PULL_REQUEST_TEMPLATE.md`: under Verification evidence, "UI screenshots: open this PR's CI run and download the `ui-screenshots` artifact (summary on the functional job)."
- Docs:
  - `docs/PROCESS.md`: one line under the verification pipeline
  - `docs/SPEC.md` and `docs/STATUS.md`
  - a `docs/HARNESS_LOG.md` entry for the CI change

Notes from implementation:
- `jobSteps` in `scripts/harness-config.test.mjs` reads this workflow's layout (jobs at two spaces, steps at six) rather than parsing YAML, so the check needs no new dependency. Its own test covers a job between two others, and a job that doesn't exist.
- The config test also asserts that nothing in `ci.yml` asks for a `write` permission.

Success criteria:
- [x] The new `harness-config` tests pass (14/14): `the functional job uploads the UI screenshots on every run`, `jobSteps reads only the named job's steps`, `the PR template tells reviewers where the UI screenshots are`
- [x] Negative proof: removing `if: always()` from the upload step failed only the CI config test, with "The ui-screenshots upload needs `if: always()`." Reverted
- [x] `npm run check` passes (see Final verification)
- [ ] **After you push the branch:** `gh run view <id>` shows a `ui-screenshots` artifact on the PR's run. Downloaded, it has 20 PNGs and is at most 5 MB. `gh api .../artifacts` shows it expires 14 days after the run
- [ ] **After you push the branch:** the functional job's summary on that run shows the "UI screenshots" section with all 20 present
- [x] `docs/SPEC.md`, `docs/STATUS.md`, `docs/PROCESS.md` and `docs/HARNESS_LOG.md` are updated

## Final verification

- [x] `npm run check` passes
- [x] Every acceptance criterion in the spec is covered by a test (table below). With Status **Done**, `scripts/harness-config.test.mjs` confirms that every name in the table matches a test
- [ ] The two CI-run criteria in Phase 3 are checked on the PR's first run, during `/ship`

### Spec coverage

Name each test as `path::test name`: a Python `def`, or a vitest title exactly as quoted. `scripts/harness-config.test.mjs` fails on a row that names no test, and, once Status is **Done**, on a name that matches no test.

| Spec acceptance criterion | Tests |
|---|---|
| 20 PNGs: 5 screens × 2 themes × 2 widths, named `<screen>-<theme>-<width>.png` | `e2e/test_screenshots.py::test_captures_every_screen`, `scripts/screenshot-summary.test.mjs::passes when all 20 screenshots are present` |
| Dark captures use the dark `--color-bg`, light ones the light one | `e2e/test_screenshots.py::test_captures_every_screen` |
| Full page, taken only when loaded: fonts ready, no skeleton, heading visible, no animation or caret | `e2e/test_screenshots.py::test_captures_every_screen` |
| Fixed sample data, no random suffixes | `e2e/test_screenshots.py::test_captures_every_screen` |
| `new-group-dialog` shows the dialog open with Name focused | `e2e/test_screenshots.py::test_captures_every_screen` |
| `not-found` is the signed-in Page not found at `/nowhere` | `e2e/test_screenshots.py::test_captures_every_screen` |
| Local runs write to `test-results/screenshots/` and change nothing else | `e2e/test_screenshots.py::test_captures_every_screen` (plus the `git status` criterion in Phase 1) |
| CI uploads `ui-screenshots` on every run, kept 14 days, `if-no-files-found: error` | `scripts/harness-config.test.mjs::the functional job uploads the UI screenshots on every run` |
| The job summary lists the 20 files and names the artifact | `scripts/screenshot-summary.test.mjs::prints a UI screenshots section that names the artifact`, `scripts/harness-config.test.mjs::the functional job uploads the UI screenshots on every run` |
| The PR template says where the screenshots are | `scripts/harness-config.test.mjs::the PR template tells reviewers where the UI screenshots are` |
| A missing or unloaded screen fails, naming it; a partial set never passes | `e2e/test_screenshots.py::test_every_screen_is_captured`, `scripts/screenshot-summary.test.mjs::fails and names a missing screenshot`, `scripts/screenshot-summary.test.mjs::fails on an unexpected file` |
| Negative proof: drop a screen and the count check fails | `e2e/test_screenshots.py::test_every_screen_is_captured`, `scripts/screenshot-summary.test.mjs::lists the same screens as the capture tests` |
| Capture calls are only the screen's own; no third-party requests | `e2e/test_screenshots.py::test_captures_every_screen` |
