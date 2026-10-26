# Spec: CI screenshot artifacts

> Status: **ready for planning**. Decisions D1–D4 are recorded at the end. It builds on the Caravan UI from `docs/specs/app-shell-and-design-system.md` (PR #3), so it can't be planned until that merges.

## Expected outcome

Every CI run captures each main screen of the app in light and dark, at phone (360 px) and desktop (1280 px) widths, from the production build the E2E tests already serve. It uploads the images as a GitHub Actions artifact named `ui-screenshots`, so a PR reviewer sees the UI the code produces rather than screenshots an agent took by hand.

## Constraints

- **No change to the existing checks.** The seven CI jobs, their names, order and pass/fail rules stay the same. The functional job's `playwright-report` artifact (uploaded on failure, kept 7 days) is unchanged.
- **Existing E2E tests are untouched.** Capturing screenshots adds no outside journey to `e2e/test_journeys.py`, so the outside/inside pairing check in `scripts/harness-config.test.mjs` is unchanged. The screenshots are evidence, not a journey.
- **Same servers, same rules.** Captures run against the servers `e2e/conftest.py` starts (fresh production build, dedicated ports, throwaway database). The `traffic` fixture's ban on third-party origins still applies. No sleeps, `networkidle` or `wait_for_timeout` (the `badWaits` scan).
- **CI permissions stay `contents: read`.** No new secrets and no write tokens (D4).
- **Captured inside the existing functional stage (D1),** by a new module `e2e/test_screenshots.py`. No new CI job and no new required check.
- **No new dependencies.** It uses pytest-playwright and the pinned `actions/upload-artifact@v7` already in `ci.yml`.
- **Harness change.** Editing `.github/workflows/ci.yml` needs the code owner's review (`.github/CODEOWNERS`) and an entry in `docs/HARNESS_LOG.md`.
- **Synthetic data only.** The screens show fixed, made-up members and groups created by the test itself, never data from a dev database.
- No lowered thresholds, suppressions or skipped tests.

## Acceptance criteria

### What gets captured

- [ ] Given a CI run, when the functional job finishes, then the `ui-screenshots` artifact has exactly 20 PNG files: 5 screens × 2 themes × 2 widths.
  - **Screens:** `sign-in`, `home`, `new-group-dialog`, `group`, `not-found`
  - **Themes:** `light`, `dark`
  - **Widths:** `360`, `1280`
  - **File names:** `<screen>-<theme>-<width>.png`, for example `group-dark-360.png`
- [ ] Given a dark capture, then the page was rendered with `prefers-color-scheme: dark`, so the body background is the dark `--color-bg`. Given a light capture, it's the light one.
- [ ] Given each capture, then it's a full-page image taken only once the screen has loaded:
  - the web font has finished loading (`document.fonts.ready`)
  - no loading skeleton is visible
  - the screen's heading is visible
  - animations are disabled and the text caret is hidden, so two runs of the same code produce the same picture
- [ ] Given the screens, then they show fixed sample data with no random suffixes:
  - the signed-in member "Ada Lovelace", owner of the group "Goa Getaway" ("Beach week in December.")
  - a pending request from "Bob Marley", so the group screen shows both Members and Pending requests
  - a second group owned by Bob, "Ladakh Road Trip", so Home shows both My groups and Browse groups
- [ ] Given `new-group-dialog`, then it shows Home with the Create group dialog open and its Name field focused.
- [ ] Given `not-found`, then it's the signed-in **Page not found** screen at `/nowhere`.

### Where they go

- [ ] Given a local run of `npm run check` or `npm run test:e2e`, then the 20 files are written to `test-results/screenshots/` (git-ignored), and the working tree is otherwise unchanged.
- [ ] Given any CI run (pull request or push to `main`, passing or failing), then `test-results/screenshots/` is uploaded as `ui-screenshots` with `if: always()`, `retention-days: 14` and `if-no-files-found: error` (D2, D3).
- [ ] Given a finished run, then the functional job's summary has a "UI screenshots" section. It lists the 20 file names by screen, theme and width, and says they're in the run's `ui-screenshots` artifact (D4).
- [ ] Given `.github/PULL_REQUEST_TEMPLATE.md`, then its verification section tells the author and reviewers to open the PR's CI run and download `ui-screenshots`.

### Guarding the guard

- [ ] Given the capture tests, when a screen is missing from the expected list or fails to load, then a test fails and names the screen. The count check doesn't pass on a partial set.
- [ ] Negative proof: temporarily drop one screen from the capture list, and the count check fails while the rest of the functional stage passes. Then revert.
- [ ] Given the capture tests, then their API calls are only those of the screens they show, checked like any other E2E test. They make no third-party requests.

## Non-functional requirements

- **Time:** the functional stage takes at most 30 s longer, locally and in CI.
- **Size:** one run's `ui-screenshots` artifact is at most 5 MB. At about 60 KB a screenshot that's about 1.2 MB, well inside the private repo's 500 MB artifact quota at 14 days' retention.
- **Security:**
  - the artifact holds only images of synthetic data, with no cookies, tokens or traces
  - the workflow token keeps `contents: read`, and the job summary needs no extra permission
  - pull requests from forks still get their artifacts, since uploading needs no write token
- **Determinism:** fixed viewport sizes, fixed data, fonts loaded and animations off. The images may still differ by a pixel between the CI runner and a local machine; nothing compares them.
- **Accessibility and cost:** no change to the app. There's no paid service.

## Failure conditions

- **The app can't start** (build, backend or preview server fails): the functional job fails as today. With `if: always()` (D2), the upload still runs, alongside `playwright-report`. If nothing was captured, `if-no-files-found: error` makes the missing evidence visible as its own failed step.
- **A screen doesn't reach its loaded state** (heading not visible, skeleton still showing): that capture fails with the screen's name, and the functional stage fails. A half-loaded screenshot is never uploaded as if it were good.
- **Fewer than 20 files:** the count check fails, and `if-no-files-found: error` fails the upload when there are none.
- **The artifact service is down or the upload fails:** the upload step fails the job, so a run never looks complete without its evidence. A re-run fixes it.
- **Captures run twice in one E2E session** (for example a retried test): the fixed user IDs and group names would collide. Capture tests create their data once per session, and a re-run in the same session overwrites the files rather than adding to them.
- **Limits:** 20 files, at most 5 MB, kept 14 days. GitHub deletes older artifacts.

## Definition of Done

- [ ] All acceptance criteria are covered by passing tests
- [ ] `npm run check` passes locally, and the CI run on the PR shows a `ui-screenshots` artifact with 20 images
- [ ] `docs/SPEC.md` and `docs/STATUS.md` are updated
- [ ] `docs/PROCESS.md` (verification pipeline) and `.github/PULL_REQUEST_TEMPLATE.md` say where the screenshots are
- [ ] `docs/HARNESS_LOG.md` has an entry for the CI change
- [ ] `code-reviewer` and `security-reviewer` have run with no unresolved findings, and the code owner has reviewed the `.github/` change

## Out of scope

- **Visual regression:** comparing images with a stored baseline and failing on a difference
- Showing images inline in the PR description or a comment (GitHub only takes image uploads through its web editor)
- Screens in other states: errors, loading, empty lists, signed-out deep links
- Other browsers, device emulation beyond the viewport width, and screenshot-based accessibility checks
- Changing the existing `playwright-report` artifact

## Decisions

Confirmed by the human on 2026-10-26.

- **D1. Where the captures run:** in the existing functional stage, through a new `e2e/test_screenshots.py`. It reuses the E2E build, servers and database. It adds about 20–30 s, needs no new CI job or required check, and also runs locally with `npm run check`.
- **D2. When the artifact is uploaded:** on every run (`if: always()`): pull requests and pushes to `main`, passing or failing, so a failed UI change can still be inspected.
- **D3. Retention:** 14 days, long enough for a PR's review cycle.
- **D4. How reviewers find it:** a "UI screenshots" section in the functional job's summary, plus a line in the PR template. The workflow token stays `contents: read`; there's no bot comment and no `pull-requests: write`.
