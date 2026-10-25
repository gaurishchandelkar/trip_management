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

## Hand over

Don't push and don't open the PR. Give the human these commands:

```bash
git push -u origin feat/$ARGUMENTS
gh pr create --title "<spec title>" --body-file .git/PR_BODY_$ARGUMENTS.md
```

After merge, suggest `/retro $ARGUMENTS`.
