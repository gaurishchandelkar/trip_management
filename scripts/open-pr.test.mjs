import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import { ghCandidates, specTitle } from "./open-pr.mjs";

test("specTitle reads the title from the spec heading", () => {
  assert.equal(
    specTitle("# Spec: App shell and design system\n\n> Status"),
    "App shell and design system",
  );
  assert.equal(specTitle("# Plan: Not a spec\n"), null);
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
