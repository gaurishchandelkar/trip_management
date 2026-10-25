// Checks that safeguards cover the code they're meant to (docs/HARNESS_LOG.md, python-e2e-whitebox retro).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
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

// Every outside journey needs an inside test that pins down its API calls
// (docs/HARNESS_LOG.md, members-and-groups retro). Inside tests say which with @covers(...).
export function journeyCoverage(journeys, contracts) {
  const names = [...journeys.matchAll(/^def (test_\w+)\(/gm)].map(([, name]) => name);
  const covered = new Set(
    [...contracts.matchAll(/^@covers\(([^)]*)\)/gm)].flatMap(([, args]) =>
      [...args.matchAll(/"(test_\w+)"/g)].map(([, name]) => name),
    ),
  );
  return {
    uncovered: names.filter((name) => !covered.has(name)),
    unknown: [...covered].filter((name) => !names.includes(name)),
  };
}

test("every outside journey has an inside network-contract test", () => {
  const { uncovered, unknown } = journeyCoverage(
    readFileSync("e2e/test_journeys.py", "utf8"),
    readFileSync("e2e/test_network_contract.py", "utf8"),
  );

  assert.deepEqual(uncovered, [], "Add an inside test with @covers(...) for these journeys.");
  assert.deepEqual(unknown, [], "These @covers names match no journey in test_journeys.py.");
});

test("journeyCoverage catches a journey without an inside test and a stale name", () => {
  const journeys = "def test_sign_in(page):\n    ...\ndef test_sign_out(page):\n    ...\n";
  const contracts = [
    '@covers("test_sign_in", "test_renamed")',
    "def test_sign_in_sends_one_request(page, traffic):",
  ].join("\n");

  assert.deepEqual(journeyCoverage(journeys, contracts), {
    uncovered: ["test_sign_out"],
    unknown: ["test_renamed"],
  });
});

// Invisible format characters (zero-width, bidirectional overrides, BOM) make source read
// differently from how it runs. Tests that need them spell them as escapes, such as \u200d.
const HIDDEN = /\p{Cf}/u;
const SOURCE = /\.(?:py|ts|tsx|js|mjs|json|toml|yml|yaml|md|css|html)$/;

export function hiddenCharacters(files) {
  return files.flatMap(([file, text]) =>
    text
      .split("\n")
      .flatMap((line, index) =>
        HIDDEN.test(line)
          ? [
              `${file}:${String(index + 1)}: U+${line.match(HIDDEN)[0].codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}`,
            ]
          : [],
      ),
  );
}

test("tracked source files contain no invisible format characters", () => {
  const tracked = execFileSync("git", ["ls-files"], { encoding: "utf8" })
    .split("\n")
    .filter((file) => SOURCE.test(file));

  const found = hiddenCharacters(tracked.map((file) => [file, readFileSync(file, "utf8")]));

  assert.deepEqual(found, [], "Write these characters as escapes (\\u200d) instead.");
});

test("hiddenCharacters reports the file, line and code point", () => {
  const files = [
    ["a.py", 'ok = "Goa"\nbad = "Go\u200da"'],
    ["b.ts", 'const escaped = "\\u202e";'],
  ];

  assert.deepEqual(hiddenCharacters(files), ["a.py:2: U+200D"]);
});
