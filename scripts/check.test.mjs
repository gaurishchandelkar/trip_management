// CI's pass or fail is check.mjs's exit code, so these run the script as CI does. A fake `npm`
// first on PATH stands in for the stages: it prints which one ran, and fails the one named in
// FAKE_FAIL.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { after, test } from "node:test";

const fakeBin = mkdtempSync(join(tmpdir(), "check-test-"));
after(() => {
  rmSync(fakeBin, { recursive: true, force: true });
});
if (process.platform === "win32") {
  writeFileSync(
    join(fakeBin, "npm.cmd"),
    '@echo ran %2\r\n@if "%2"=="%FAKE_FAIL%" exit /b 3\r\n@exit /b 0\r\n',
  );
} else {
  writeFileSync(
    join(fakeBin, "npm"),
    '#!/bin/sh\necho "ran $2"\n[ "$2" = "$FAKE_FAIL" ] && exit 3\nexit 0\n',
    { mode: 0o755 },
  );
}

function check(args, fail = "") {
  const env = { ...process.env, FAKE_FAIL: fail };
  const pathKey = Object.keys(env).find((key) => key.toUpperCase() === "PATH") ?? "PATH";
  env[pathKey] = `${fakeBin}${delimiter}${env[pathKey] ?? ""}`;
  const { status, stdout, stderr } = spawnSync(process.execPath, ["scripts/check.mjs", ...args], {
    cwd: realpathSync.native(process.cwd()),
    encoding: "utf8",
    env,
  });
  return { status, ran: [...stdout.matchAll(/^ran (\S+)/gm)].map(([, s]) => s), stdout, stderr };
}

test("runs every stage in order and exits 0 when they all pass", () => {
  const { status, ran, stdout } = check([]);

  assert.equal(status, 0);
  assert.deepEqual(ran, [
    "build",
    "lint",
    "test:unit",
    "test:integration",
    "test:e2e",
    "security",
    "architecture",
  ]);
  assert.match(stdout, /All stages passed\./);
});

test("stops at the first failing stage and exits 1, naming it", () => {
  const { status, ran, stdout, stderr } = check([], "test:unit");

  assert.equal(status, 1);
  assert.deepEqual(ran, ["build", "lint", "test:unit"]);
  assert.match(stderr, /FAIL {2}unit/);
  assert.match(stderr, /Stage "unit" failed/);
  assert.doesNotMatch(stdout, /All stages passed/);
});

test("runs only the stages asked for", () => {
  const { status, ran } = check(["lint", "architecture"]);

  assert.equal(status, 0);
  assert.deepEqual(ran, ["lint", "architecture"]);
});

test("exits 2 on an unknown stage without running any", () => {
  const { status, ran, stderr } = check(["lint", "e2e"]);

  assert.equal(status, 2);
  assert.deepEqual(ran, []);
  assert.match(stderr, /Unknown stage\(s\): e2e/);
});
