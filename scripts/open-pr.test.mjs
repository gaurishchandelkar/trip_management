import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import {
  changesUi,
  ghCandidates,
  screenshotAttachments,
  specTitle,
  titleAndBody,
} from "./open-pr.mjs";
import { EXPECTED } from "./screenshot-summary.mjs";

const DIR = "test-results/screenshots";
const captured = (mtimeMs) => EXPECTED.map((name) => ({ name, mtimeMs }));

test("changesUi is true only for frontend code or the screenshot captures", () => {
  assert.equal(changesUi(["docs/STATUS.md", "frontend/src/App.tsx"]), true);
  assert.equal(changesUi(["e2e/test_screenshots.py"]), true);
  assert.equal(changesUi(["README.md", "e2e/test_journeys.py", "frontendish.md", ""]), false);
});

test("screenshotAttachments attaches the 20 e2e captures in screen order, with alt text", () => {
  const { args, error } = screenshotAttachments(DIR, captured(2000).reverse(), 1000);

  assert.equal(error, undefined);
  assert.equal(args.length, 40);
  assert.deepEqual(args.slice(0, 4), [
    "--attach",
    `${DIR}/sign-in-light-360.png#sign in, light, 360 px`,
    "--attach",
    `${DIR}/sign-in-light-1280.png#sign in, light, 1280 px`,
  ]);
  assert.equal(args.at(-1), `${DIR}/not-found-dark-1280.png#not found, dark, 1280 px`);
});

test("screenshotAttachments refuses a partial, padded or stale set", () => {
  const partial = captured(2000).slice(1);
  const padded = [...captured(2000), { name: "trace.zip", mtimeMs: 2000 }];
  const stale = captured(2000).map((file, i) => (i === 3 ? { ...file, mtimeMs: 500 } : file));

  assert.match(screenshotAttachments(DIR, partial, 1000).error ?? "", /exactly the 20 captures/);
  assert.match(screenshotAttachments(DIR, padded, 1000).error ?? "", /exactly the 20 captures/);
  assert.match(screenshotAttachments(DIR, [], 1000).error ?? "", /npm run check -- functional/);
  assert.match(screenshotAttachments(DIR, stale, 1000).error ?? "", /older than this branch's/);
});

test("specTitle reads the title from the spec heading", () => {
  assert.equal(
    specTitle("# Spec: App shell and design system\n\n> Status"),
    "App shell and design system",
  );
  assert.equal(specTitle("# Plan: Not a spec\n"), null);
});

test("titleAndBody takes a spec's title, and keeps its body whole", () => {
  const body = "## Summary\n\nDone.\n";

  assert.deepEqual(titleAndBody("# Spec: Members and groups\n", body), {
    title: "Members and groups",
    body,
  });
  assert.equal(titleAndBody("# Plan: not a spec\n", body), null);
});

test("titleAndBody takes the title from the body's heading, even when a spec has the name", () => {
  const expected = { title: "Retro: CI screenshots", body: "## Summary\n\nDone.\n" };
  const bom = String.fromCodePoint(0xfeff);

  assert.deepEqual(
    titleAndBody(null, "# Retro: CI screenshots\r\n\r\n## Summary\n\nDone.\n"),
    expected,
  );
  // A retro of a spec is named after the spec, but its heading still names the PR.
  assert.deepEqual(
    titleAndBody("# Spec: S\n", "# Retro: CI screenshots\n\n## Summary\n\nDone.\n"),
    expected,
  );
  assert.deepEqual(
    titleAndBody(null, `${bom}# Retro: CI screenshots  \n## Summary\n\nDone.\n`),
    expected,
  );
  assert.deepEqual(titleAndBody(null, "# Only a title"), { title: "Only a title", body: "" });
});

test("titleAndBody refuses a body with no usable heading and no spec", () => {
  assert.equal(titleAndBody(null, "## Summary\n\n# Not first\n"), null);
  assert.equal(titleAndBody(null, "#    \n\nBody\n"), null);
  assert.equal(titleAndBody(null, ""), null);
});

test("every spec has a title the PR can use", () => {
  const specs = readdirSync("docs/specs").filter((file) => file.endsWith(".md"));
  assert.ok(specs.length > 0);

  for (const file of specs) {
    assert.ok(specTitle(readFileSync(`docs/specs/${file}`, "utf8")), `docs/specs/${file}`);
  }
});

test("ghCandidates also looks where Windows installs gh, outside Git Bash's PATH", () => {
  assert.deepEqual(ghCandidates("linux", {}), ["gh"]);
  assert.deepEqual(
    ghCandidates("win32", {
      ProgramFiles: "C:\\Program Files",
      LOCALAPPDATA: "C:\\Users\\a\\AppData\\Local",
    }),
    [
      "gh",
      "C:\\Program Files\\GitHub CLI\\gh.exe",
      "C:\\Users\\a\\AppData\\Local\\Programs\\GitHub CLI\\gh.exe",
    ],
  );
});
