---
name: ship
description: Prepare a finished branch for human review - full checks, reviewer subagents, and a PR description. Agents never push; the human opens the PR.
argument-hint: <plan name>
---

# /ship: Stage 5, Ship

Prepare `feat/$ARGUMENTS` for review.

## Steps

1. Run `npm run check`. If any stage fails, stop and fix it (or go back to `/implement`).
2. Run the **code-reviewer** and **security-reviewer** subagents in parallel on `git diff main...HEAD`.
3. Fix every blocking finding and commit the fixes. List the non-blocking findings you didn't fix in the PR description.
4. Write the PR description to `.git/PR_BODY_$ARGUMENTS.md` using `.github/PULL_REQUEST_TEMPLATE.md`:
   - Link the spec and plan, and copy their **Human attention needed** items.
   - Paste the final `npm run check` stage summary as evidence.
   - Fill in the agent metrics: phases, commits, and fix-up commits after a failed check.
5. If the change touches `frontend/` or `e2e/test_screenshots.py`, the PR shows the 20 e2e captures from `test-results/screenshots/`, not screenshots you take by hand. Make sure they're fresh: if you committed UI fixes after step 1, or ran a pytest stage since (pytest-playwright empties `test-results/`), run `npm run check -- functional` again. Don't put a placeholder for them in the body: `npm run pr` attaches them below it.

## Hand over

Don't push and don't open the PR. Give the human these commands, one per line, each short enough not to wrap:

```bash
git push -u origin feat/$ARGUMENTS
npm run pr -- $ARGUMENTS
```

`npm run pr` takes the title from the spec, the body from `.git/PR_BODY_$ARGUMENTS.md` and, for a UI change, the e2e captures from `test-results/screenshots/`. It refuses a partial set, or one older than the branch's last UI commit. It finds `gh` even where Git Bash can't.

After merge, suggest `/retro $ARGUMENTS`.
