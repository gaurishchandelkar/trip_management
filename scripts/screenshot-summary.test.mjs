import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
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

test("never prints a file name that could inject Markdown into the summary", () => {
  const crafted = [
    "x`[Click to re-run](https://evil.example)`.png",
    "x.png\n## Approved by security",
  ];
  const { markdown, unexpected } = summarize([...EXPECTED, ...crafted, "notes.txt"]);

  assert.equal(unexpected.length, 3);
  assert.match(markdown, /Unexpected files: `notes.txt`, 2 more with unusual names$/m);
  assert.doesNotMatch(markdown, /evil\.example|Approved by security/);
});

test("says there is no artifact when nothing was captured", () => {
  const { markdown, ok } = summarize([]);

  assert.equal(ok, false);
  assert.match(
    markdown,
    /No screenshots were captured, so this run has no `ui-screenshots` artifact/,
  );
  assert.doesNotMatch(markdown, /\| Screen \|/);
});

// CI's summary step depends on the exit code, so run the script as CI does.
function runScript(...args) {
  return spawnSync(process.execPath, ["scripts/screenshot-summary.mjs", ...args], {
    encoding: "utf8",
  });
}

test("exits 0 for the full set and 1 for a partial or missing one, as CI runs it", () => {
  const dir = mkdtempSync(join(tmpdir(), "screenshots-"));
  try {
    for (const file of EXPECTED) writeFileSync(join(dir, file), "");
    const full = runScript(dir);
    assert.equal(full.status, 0, full.stderr);
    assert.match(full.stdout, /^## UI screenshots$/m);

    rmSync(join(dir, "group-dark-360.png"));
    const partial = runScript(dir);
    assert.equal(partial.status, 1);
    assert.match(partial.stderr, /Missing: group-dark-360\.png\./);
    assert.doesNotMatch(partial.stdout, /incomplete/);

    assert.equal(runScript(join(dir, "does-not-exist")).status, 1);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
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
