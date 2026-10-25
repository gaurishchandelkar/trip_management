// Applies branch protection to main with the GitHub CLI. Run by a human repo admin, never by an agent.
// Usage: node scripts/protect-branch.mjs [--solo] [branch]
//   --solo  for a repo with one maintainer: PRs and every CI stage are still required, but no
//           approving review, because GitHub doesn't let you approve your own PR.
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

export const CHECKS = [
  "build",
  "lint",
  "unit",
  "integration",
  "functional",
  "security",
  "architecture",
];

export function protection({ solo }) {
  return {
    required_status_checks: { strict: true, contexts: CHECKS },
    enforce_admins: true,
    required_pull_request_reviews: {
      required_approving_review_count: solo ? 0 : 1,
      require_code_owner_reviews: !solo,
      dismiss_stale_reviews: true,
    },
    restrictions: null,
    required_linear_history: true,
    allow_force_pushes: false,
    allow_deletions: false,
  };
}

function main() {
  const { values, positionals } = parseArgs({
    options: { solo: { type: "boolean", default: false } },
    allowPositionals: true,
  });
  const branch = positionals[0] ?? "main";
  const repo = execFileSync(
    "gh",
    ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
    { encoding: "utf8" },
  ).trim();

  execFileSync(
    "gh",
    ["api", "-X", "PUT", `repos/${repo}/branches/${branch}/protection`, "--input", "-"],
    {
      input: JSON.stringify(protection({ solo: values.solo })),
      // Drop gh's echo of the full protection JSON; keep stderr for GitHub's error messages.
      stdio: ["pipe", "ignore", "inherit"],
    },
  );
  const reviews = values.solo ? "no approval (solo)" : "code owner review";
  console.log(`Protected ${repo}@${branch}: PRs, ${reviews} and all CI stages required.`);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) main();
