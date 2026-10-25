# Rules

These are the primary operating rules for agents in this repo. They come first, and the other documents add detail.

## Principles

1. **Autonomy follows verification.** You can act freely wherever `npm run check` can confirm the result. Where it can't, ask.
2. **Intent comes first.** Build what the spec says. Don't add features, refactors or abstractions nobody asked for.
3. **Evidence over assertion.** "Done" means the success criteria are ticked and the checks pass, not that the code looks right.
4. **Fix the harness, not just the bug.** Every failure is a chance to improve the rules, safeguards or tests (see Flywheel below).

## Hard rules

Where a rule can be enforced, it's enforced by a tool and not just written here.

| Rule | Enforced by |
|---|---|
| Never push to any remote | `.claude/settings.json` deny rule, guard hook, branch protection |
| Never skip hooks (`--no-verify`, `-n`, `LEFTHOOK=0`) | Guard hook, CI re-runs every check |
| Never lower a coverage threshold or disable a lint/type rule | Guard hook blocks suppression comments; CI and the `code-reviewer` subagent review config diffs |
| Never read, write or print `.env*` files or secrets | `.claude/settings.json` deny rules, guard hook, detect-secrets |
| Never break the layer order (`api` → `services` → `domain`) | import-linter, ESLint import rules |
| Every change ships with tests | Coverage gates (80%) in `npm run check` |
| Tests never call external networks or paid APIs | Code review, stub/fake dependencies |
| Run `npm run check` before handing over | Pre-commit hook (fast stages), CI (all stages) |
| Never commit straight to `main` once a remote exists | Branch protection |

## Stop and ask when

- A rule or check seems wrong. Explain why and propose a change; don't work around it.
- The spec is ambiguous, or it conflicts with the code or another document.
- A change touches security, authentication, data deletion, dependencies or CI config.
- You've failed the same check three times in a row.

## Definition of Done

- [ ] Every acceptance criterion in the spec is met and every success criterion in the plan is ticked
- [ ] Tests are added or updated, and `npm run check` passes
- [ ] `docs/STATUS.md` and any affected docs (`SPEC.md`, `TECH_STACK.md`) are updated
- [ ] Work is committed with a clear message, and the hooks passed

## Flywheel

When something escapes or goes wrong, record it in `docs/HARNESS_LOG.md` and improve the harness:

| Feedback signal | Harness improvement |
|---|---|
| Escaped defect | New test |
| Architecture violation | New rule (and an import contract) |
| Security issue | New safeguard |
| Repeated review feedback | Updated coding guidelines |
| Repetitive engineering task | New agent skill |
| Successful pattern | Reusable skill or template |
| Harness defect (a check, hook or metric gave false or misleading evidence) | Fix it, with a test proving the fix |
