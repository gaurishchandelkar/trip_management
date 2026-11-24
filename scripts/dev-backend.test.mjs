import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { backendArgs, ENV_FILE } from "./dev-backend.mjs";

const SERVER = ["-m", "uvicorn", "backend.main:app", "--reload", "--reload-dir", "backend"];

test("loads the env file when there is one", () => {
  assert.deepEqual(backendArgs(true), ["run", "--env-file", ".env", ...SERVER]);
  assert.equal(ENV_FILE, ".env");
});

// uv exits with "No environment file found" for a missing --env-file, which would stop a
// fresh clone from running the dev server at all.
test("passes no env file when there isn't one", () => {
  assert.deepEqual(backendArgs(false), ["run", ...SERVER]);
});

test("npm run dev starts the backend through this script", () => {
  const scripts = JSON.parse(readFileSync("package.json", "utf8")).scripts;
  assert.equal(scripts["dev:backend"], "node scripts/dev-backend.mjs");
  assert.match(scripts.dev, /npm:dev:backend/);
});

// The file holds secrets: it must stay out of git (docs/SECURITY_GUIDELINES.md).
test("the env file is git-ignored", () => {
  const ignored = readFileSync(".gitignore", "utf8").split(/\r?\n/);
  assert.ok(ignored.includes(ENV_FILE), ".gitignore must list the env file");
});
