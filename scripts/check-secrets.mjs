// Scans the given files (default: all tracked files) for secrets not in .secrets.baseline.
import { execFileSync, spawnSync } from "node:child_process";

const files =
  process.argv.length > 2
    ? process.argv.slice(2)
    : execFileSync("git", ["ls-files"], { encoding: "utf8" }).split("\n").filter(Boolean);

const BATCH = 200;
let failed = false;
for (let i = 0; i < files.length; i += BATCH) {
  const result = spawnSync(
    "uv",
    ["run", "detect-secrets-hook", "--baseline", ".secrets.baseline", ...files.slice(i, i + BATCH)],
    { stdio: "inherit" },
  );
  if (result.status !== 0) failed = true;
}

if (failed) {
  console.error(
    "\nPossible secrets found. Remove them, or if a finding is a false positive, ask a human to audit the baseline.",
  );
  process.exit(1);
}
console.log(`detect-secrets: ${files.length} files clean`);
