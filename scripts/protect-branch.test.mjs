import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { CHECKS, protection } from "./protect-branch.mjs";

test("team mode requires a code owner approval and every CI stage", () => {
  const rules = protection({ solo: false });

  assert.equal(rules.required_pull_request_reviews.required_approving_review_count, 1);
  assert.equal(rules.required_pull_request_reviews.require_code_owner_reviews, true);
  assert.deepEqual(rules.required_status_checks.contexts, CHECKS);
});

// A lone maintainer can't approve their own PR, so requiring one locks main for good.
test("solo mode needs no approval but still requires PRs and every CI stage", () => {
  const rules = protection({ solo: true });

  assert.equal(rules.required_pull_request_reviews.required_approving_review_count, 0);
  assert.equal(rules.required_pull_request_reviews.require_code_owner_reviews, false);
  assert.deepEqual(rules.required_status_checks.contexts, CHECKS);
  assert.equal(rules.enforce_admins, true);
});

test("the required checks match the CI job names", () => {
  const ci = readFileSync(".github/workflows/ci.yml", "utf8");
  const jobsBlock = ci.slice(ci.indexOf("\njobs:\n"));
  const jobs = [...jobsBlock.matchAll(/^ {2}([a-z]+):$/gm)].map(([, name]) => name);

  assert.deepEqual([...jobs].sort(), [...CHECKS].sort());
});
