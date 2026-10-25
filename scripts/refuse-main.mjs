// Pre-commit check: refuses commits straight to main once a remote exists (docs/RULES.md).
// GitHub branch protection needs a public repo or GitHub Pro, so this enforces the rule locally.
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

export const PROTECTED_BRANCHES = ["main"];

export function refusal(branch, remotes) {
  if (!PROTECTED_BRANCHES.includes(branch) || remotes.length === 0) return null;
  return `Never commit straight to ${branch}. Create a branch: git switch -c feat/<name>`;
}

function git(...args) {
  return execFileSync("git", args, { encoding: "utf8" }).trim();
}

function main() {
  const reason = refusal(
    git("branch", "--show-current"),
    git("remote").split("\n").filter(Boolean),
  );
  if (reason) {
    console.error(reason);
    process.exitCode = 1;
  }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) main();
