# Metrics

Hyper productivity isn't more code. Commits, lines, prompts and PR counts are cheap to inflate.
The measure that matters is **Time to Validated Outcome**: how fast a stated intent becomes a change that has passed verification and been accepted.

## What we track

| Metric | Definition | Source |
|---|---|---|
| Requirement-to-done time | Spec first committed → plan marked **Done** | `npm run metrics` (git) |
| Requirement-to-PR time | Spec first committed → PR opened | GitHub PR data |
| First-pass validation rate | Share of plan phases committed without a fix-up commit | `npm run metrics` (git) |
| Agent retry rate | Fix-up commits per phase | `npm run metrics` (git) |
| Human review effort | Review comments and rounds per PR | GitHub PR data |
| PM rework rate | Specs changed after the plan was approved | `npm run metrics` (git) |
| Regression escape rate | `docs/HARNESS_LOG.md` entries of type *escaped defect* per feature | `npm run metrics` (log) |
| Cost per accepted change | Agent spend / merged PRs | Provider billing |
| Lead time to production | Merge → deploy | Deploy pipeline (not in this template) |

**Harness growth** (tests, harness log entries, skills) is tracked too. It shows knowledge moving from people's heads into the environment the agent works in.

## Conventions the metrics rely on

- Specs live in `docs/specs/<name>.md`, and plans live in `docs/plans/PLAN_<name>.md`.
- A plan's status line changes to `Status: **Done**` in the commit that finishes it.
- Phase commits start with `<name>: phase N`. Commits that fix a failed check start with `<name>: fix`.
- The PR template's **Agent metrics** table records the same numbers for each PR.

## Running

```bash
npm run metrics
```

## Using the numbers

Track trends, not targets. A falling first-pass rate or a rising escape rate points to a gap in the harness. Run `/retro` and improve the rules, safeguards or tests rather than adding more review.
