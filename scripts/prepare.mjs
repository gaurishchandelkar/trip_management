// Runs on npm install: installs git hooks and, outside CI, the Chromium the Python E2E tests use.
// Needs uv on PATH. --frozen installs Python Playwright from uv.lock without re-resolving it.
import { execSync } from "node:child_process";

execSync("npx lefthook install", { stdio: "inherit" });
if (!process.env.CI) execSync("uv run --frozen playwright install chromium", { stdio: "inherit" });
