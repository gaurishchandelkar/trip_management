import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { evaluate, SHELL_TOOLS } from "./guard.mjs";

const P = process.cwd();

const cases = [
  ["Bash", { command: "git push origin main" }, "deny"],
  ["Bash", { command: "git -C . push" }, "deny"],
  ["Bash", { command: "git stash push" }, null],
  ["Bash", { command: 'git commit -m "x" --no-verify' }, "deny"],
  ["Bash", { command: 'git commit -n -m "x"' }, "deny"],
  ["Bash", { command: 'git commit -m "add -name flag"' }, null],
  ["Bash", { command: "LEFTHOOK=0 git commit -m x" }, "deny"],
  ["Bash", { command: "cat .env" }, "deny"],
  ["Bash", { command: "cat backend/.env.local" }, "deny"],
  ["Bash", { command: "cat .env.example" }, null],
  ["Bash", { command: "source .venv/bin/activate" }, null],
  ["Bash", { command: "node -e 'console.log(process.env.HOME)'" }, null],
  ["Bash", { command: "echo x > .claude/settings.json" }, "ask"],
  ["Bash", { command: "npm run check" }, null],
  ["PowerShell", { command: "git push origin main" }, "deny"],
  ["PowerShell", { command: 'git commit -m "x" --no-verify' }, "deny"],
  ["PowerShell", { command: "$env:LEFTHOOK = '0'; git commit -m x" }, "deny"],
  ["PowerShell", { command: "Get-Content .env" }, "deny"],
  ["PowerShell", { command: 'Get-Content -Path ".env.local"' }, "deny"],
  ["PowerShell", { command: "Get-Content .env.example" }, null],
  ["PowerShell", { command: "Write-Output $env:PATH" }, null],
  ["PowerShell", { command: "Set-Content .claude/settings.json '{}'" }, "ask"],
  ["PowerShell", { command: "Remove-Item .github\\workflows\\ci.yml" }, "ask"],
  ["PowerShell", { command: "git status; npm run check" }, null],
  ["Read", { file_path: `${P}/.env` }, "deny"],
  ["Read", { file_path: `${P}/.env.example` }, null],
  ["Write", { file_path: `${P}/backend/x.py`, content: "x = 1  # noqa" }, "deny"],
  [
    "Edit",
    { file_path: `${P}/frontend/src/a.ts`, new_string: "// eslint-disable-next-line" },
    "deny",
  ],
  ["Edit", { file_path: `${P}/frontend/src/a.ts`, new_string: "// @ts-expect-error" }, "deny"],
  ["Edit", { file_path: `${P}/docs/CODING_GUIDELINES.md`, new_string: "never `# noqa`" }, null],
  ["Edit", { file_path: `${P}/pyproject.toml`, new_string: "fail_under = 50" }, "deny"],
  ["Edit", { file_path: `${P}/pyproject.toml`, new_string: "fail_under = 85" }, null],
  ["Edit", { file_path: `${P}/pyproject.toml`, new_string: '"e2e/conftest.py" = ["S603"]' }, "ask"],
  [
    "Edit",
    { file_path: `${P}/pyproject.toml`, new_string: "[tool.ruff.lint.per-file-ignores]" },
    "ask",
  ],
  ["Edit", { file_path: `${P}/pyproject.toml`, new_string: 'extend-exclude = ["x"]' }, "ask"],
  ["Edit", { file_path: `${P}/pyproject.toml`, new_string: 'ignore = ["E501"]' }, "ask"],
  [
    "Edit",
    { file_path: `${P}/pyproject.toml`, new_string: "reportUnknownMemberType = false" },
    "ask",
  ],
  ["Edit", { file_path: `${P}/pyproject.toml`, new_string: 'typeCheckingMode = "basic"' }, "ask"],
  ["Edit", { file_path: `${P}/pyproject.toml`, new_string: 'include = ["backend", "e2e"]' }, null],
  ["Edit", { file_path: `${P}/pyproject.toml`, new_string: '    "fastapi>=0.162.0",' }, null],
  ["Edit", { file_path: `${P}/backend/x.toml`, new_string: 'ignore = ["E501"]' }, null],
  [
    "Edit",
    { file_path: `${P}/frontend/vite.config.ts`, new_string: "thresholds: { lines: 60 }" },
    "deny",
  ],
  ["Edit", { file_path: `${P}/.claude/settings.json`, new_string: "{}" }, "ask"],
  ["Edit", { file_path: `${P}/docs/RULES.md`, new_string: "x" }, "ask"],
  ["Edit", { file_path: `${P}/backend/services/greeting.py`, new_string: "x" }, null],
];

for (const [toolName, toolInput, expected] of cases) {
  const subject = toolInput.command ?? toolInput.file_path.replace(P, ".");
  test(`${toolName} ${subject} -> ${String(expected)}`, () => {
    const result = evaluate({ tool_name: toolName, tool_input: toolInput }, P);
    assert.equal(result?.decision ?? null, expected);
  });
}

// The guard only sees tools the hook matcher routes to it. A shell tool missing there bypasses every rule.
test("settings route every shell tool through the guard and deny push for each", () => {
  const settings = JSON.parse(readFileSync(".claude/settings.json", "utf8"));
  const matchers = settings.hooks.PreToolUse.map((entry) => entry.matcher.split("|"));
  const guarded = matchers.find((names) => names.includes("Read")) ?? [];

  for (const tool of SHELL_TOOLS) {
    assert.ok(guarded.includes(tool), `${tool} is not routed through the guard`);
    assert.ok(settings.permissions.deny.includes(`${tool}(git push *)`), `${tool} can push`);
  }
});
