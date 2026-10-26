import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { EXPECTED, SCREENS, summarize, THEMES, WIDTHS } from "./screenshot-summary.mjs";

test("passes when all 20 screenshots are present", () => {
  const result = summarize([...EXPECTED].reverse());

  assert.equal(EXPECTED.length, 20);
  assert.ok(EXPECTED.includes("group-dark-360.png"));
  assert.deepEqual([result.ok, result.missing, result.unexpected], [true, [], []]);
});

test("prints a UI screenshots section that names the artifact", () => {
  const { markdown } = summarize(EXPECTED);

  assert.match(markdown, /^## UI screenshots$/m);
  assert.match(markdown, /20 of 20 screenshots, in this run's `ui-screenshots` artifact/);
  assert.match(markdown, /^\| new-group-dialog \| yes \| yes \| yes \| yes \|$/m);
  assert.doesNotMatch(markdown, /missing/);
});

test("fails and names a missing screenshot", () => {
  const result = summarize(EXPECTED.filter((file) => file !== "home-dark-1280.png"));

  assert.equal(result.ok, false);
  assert.deepEqual(result.missing, ["home-dark-1280.png"]);
  assert.match(result.markdown, /19 of 20 screenshots/);
  assert.match(result.markdown, /^\| home \| yes \| yes \| yes \| \*\*missing\*\* \|$/m);
});

test("fails on an unexpected file", () => {
  const result = summarize([...EXPECTED, "home-sepia-360.png"]);

  assert.equal(result.ok, false);
  assert.deepEqual(result.unexpected, ["home-sepia-360.png"]);
  assert.match(result.markdown, /Unexpected files: `home-sepia-360.png`/);
});

test("lists the same screens as the capture tests", () => {
  const captures = readFileSync("e2e/test_screenshots.py", "utf8");
  const tuple = (name) => {
    const body = new RegExp(`^${name} = \\(([^)]*)\\)`, "m").exec(captures)?.[1] ?? "";
    return body
      .split(",")
      .map((item) => item.trim().replaceAll('"', ""))
      .filter(Boolean);
  };

  assert.deepEqual(tuple("SCREENS"), SCREENS);
  assert.deepEqual(tuple("THEMES"), THEMES);
  assert.deepEqual(tuple("WIDTHS").map(Number), WIDTHS);
});
