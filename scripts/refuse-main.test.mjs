import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { refusal } from "./refuse-main.mjs";

test("refuses a commit on main once a remote exists", () => {
  assert.match(refusal("main", ["origin"]) ?? "", /Never commit straight to main/);
});

test("allows feature branches, and main before any remote exists", () => {
  assert.equal(refusal("feat/members-and-groups", ["origin"]), null);
  assert.equal(refusal("main", []), null);
});

// The check only protects main if pre-commit actually runs it.
test("lefthook pre-commit runs the main-branch check", () => {
  assert.match(readFileSync("lefthook.yml", "utf8"), /run: node scripts\/refuse-main\.mjs/);
});
