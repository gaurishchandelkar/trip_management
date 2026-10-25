// The verification pipeline from docs/PROCESS.md. Runs stages in order and stops at the first failure.
// Usage: npm run check            all stages
//        npm run check -- lint unit   selected stages
import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";

// Windows paths are case-insensitive but Vite's module graph is not: a mis-cased cwd loads
// vitest twice and fails with "Invalid Chai property". Fail early with the actual cause.
const realCwd = realpathSync.native(process.cwd());
if (realCwd !== process.cwd()) {
  console.error(`Working directory casing differs from the real path:
  shell: ${process.cwd()}
  real:  ${realCwd}
cd to the real path and run again.`);
  process.exit(2);
}

const STAGES = {
  build: "npm run build",
  lint: "npm run lint",
  unit: "npm run test:unit",
  integration: "npm run test:integration",
  functional: "npm run test:e2e",
  security: "npm run security",
  architecture: "npm run architecture",
};

const requested = process.argv.slice(2);
const unknown = requested.filter((stage) => !(stage in STAGES));
if (unknown.length > 0) {
  console.error(
    `Unknown stage(s): ${unknown.join(", ")}. Stages: ${Object.keys(STAGES).join(", ")}`,
  );
  process.exit(2);
}

const results = [];
for (const stage of requested.length > 0 ? requested : Object.keys(STAGES)) {
  console.log(`\n=== ${stage} ===`);
  const started = Date.now();
  const { status } = spawnSync(STAGES[stage], { stdio: "inherit", shell: true });
  const seconds = ((Date.now() - started) / 1000).toFixed(1);
  results.push(`${status === 0 ? "PASS" : "FAIL"}  ${stage} (${seconds}s)`);
  if (status !== 0) {
    console.error(`\n${results.join("\n")}\n\nStage "${stage}" failed. Fix it before continuing.`);
    process.exit(1);
  }
}
console.log(`\n${results.join("\n")}\n\nAll stages passed.`);
