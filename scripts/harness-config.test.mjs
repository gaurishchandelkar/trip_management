// Checks that safeguards cover the code they're meant to (docs/HARNESS_LOG.md, python-e2e-whitebox retro).
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

// Folders pyright type-checks, from pyproject.toml's [tool.pyright] include.
function pyrightDirs(pyproject) {
  const section = pyproject.slice(pyproject.indexOf("[tool.pyright]"));
  const include = /^include = \[(.*)\]$/m.exec(section)?.[1] ?? "";
  return [...include.matchAll(/"([^"]+)"/g)].map(([, dir]) => dir);
}

// Glob patterns of lefthook's pre-commit python job.
function lefthookPythonGlobs(lefthook) {
  const job = lefthook.slice(lefthook.indexOf("- name: python"));
  const glob = /^\s+glob: (.*)$/m.exec(job)?.[1] ?? "";
  return [...glob.matchAll(/"([^"]+)"/g)].map(([, pattern]) => pattern);
}

export function unlintedPythonDirs(pyproject, lefthook) {
  const globs = lefthookPythonGlobs(lefthook);
  return pyrightDirs(pyproject).filter((dir) => !globs.some((g) => g.startsWith(`${dir}/`)));
}

// networkidle settles once per navigation, so it misses calls caused by a later click.
const BAD_WAIT = /networkidle|wait_for_timeout|time\.sleep/;

export function badWaits(source) {
  return source.split("\n").filter((line) => BAD_WAIT.test(line) && !/^\s*#/.test(line));
}

test("pre-commit lints every Python folder pyright checks", () => {
  const missing = unlintedPythonDirs(
    readFileSync("pyproject.toml", "utf8"),
    readFileSync("lefthook.yml", "utf8"),
  );

  assert.deepEqual(missing, [], `Add these to lefthook.yml's python glob: ${missing.join(", ")}`);
});

test("unlintedPythonDirs catches a folder missing from the hook", () => {
  const pyproject = '[tool.pyright]\ninclude = ["backend", "e2e"]\n';
  const lefthook = '    - name: python\n      glob: "backend/**/*.py"\n';

  assert.deepEqual(unlintedPythonDirs(pyproject, lefthook), ["e2e"]);
});

test("E2E tests wait for expected responses, never by load state or sleep", () => {
  const offenders = readdirSync("e2e")
    .filter((file) => /^test_.*\.py$/.test(file))
    .flatMap((file) => badWaits(readFileSync(`e2e/${file}`, "utf8")).map((l) => `${file}: ${l}`));

  assert.deepEqual(offenders, [], "Use page.expect_response (docs/CODING_GUIDELINES.md).");
});

test("badWaits catches networkidle and sleeps", () => {
  const source = [
    '    page.wait_for_load_state("networkidle")',
    "    page.wait_for_timeout(500)",
    "    # networkidle is banned here",
    "    with page.expect_response(is_greeting):",
  ].join("\n");

  assert.equal(badWaits(source).length, 2);
});
