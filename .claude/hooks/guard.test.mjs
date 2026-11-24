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
  // Shell writes that would skip the content checks ask (members-and-groups retro)
  ["Bash", { command: `python -c "open('pyproject.toml','w').write(x)"` }, "ask"],
  ["Bash", { command: "sed -i 's/fail_under = 80/fail_under = 0/' pyproject.toml" }, "ask"],
  ["Bash", { command: "echo 'x = 1  # noqa' >> backend/x.py" }, "ask"],
  ["PowerShell", { command: "Set-Content package.json -Value $json" }, "ask"],
  // Shell edits of source, tests and docs ask: rule 6 (sso-registration retro)
  ["Bash", { command: "sed -i 's/a/b/' backend/services/auth.py" }, "ask"],
  ["Bash", { command: "python - <<'EOF'\nPath(\"docs/SPEC.md\").write_text(t)\nEOF" }, "ask"],
  ["Bash", { command: "cat > docs/notes.md <<'EOF'\nx\nEOF" }, "ask"],
  ["Bash", { command: "perl -pi -e 's/a/b/' frontend/src/App.tsx" }, "ask"],
  ["Bash", { command: "echo x | tee e2e/x.py" }, "ask"],
  ["Bash", { command: `node -e "fs.writeFileSync('scripts/x.mjs', s)"` }, "ask"],
  ["Bash", { command: "echo x >> README.md" }, "ask"],
  ["PowerShell", { command: "Set-Content CLAUDE.md 'x'" }, "ask"],
  ["Bash", { command: "cat > /c/Data/x/trip_management/docs/notes.md <<'EOF'\nx\nEOF" }, "ask"],
  ["Bash", { command: 'echo x > "$PWD/docs/x.md"' }, "ask"],
  ["Bash", { command: "echo x 2>docs/x.md" }, "ask"],
  ["Bash", { command: "echo '# noqa' 1> backend/x.py" }, "ask"],
  ["Bash", { command: "sed -Ei 's/a/b/' backend/x.py" }, "ask"],
  ["Bash", { command: "sed --in-place 's/a/b/' backend/x.py" }, "ask"],
  ["Bash", { command: "sed -e 's|a|b|' -i backend/x.py" }, "ask"],
  ["Bash", { command: "perl -p -i -e 's/a/b/' backend/x.py" }, "ask"],
  ["Bash", { command: `python -c "Path('docs/x.md').write_bytes(b)"` }, "ask"],
  ["Bash", { command: `node -e "fs.appendFileSync('scripts/x.mjs', s)"` }, "ask"],
  ["PowerShell", { command: "[IO.File]::WriteAllText('docs/x.md', $s)" }, "ask"],
  ["PowerShell", { command: "Get-Content a.txt | Out-File docs/x.md" }, "ask"],
  // ...while reading, searching, test runs and other paths stay silent
  ["Bash", { command: "sed -n '1,5p' backend/main.py" }, null],
  ["Bash", { command: "uv run pytest backend/tests > test-output.txt" }, null],
  ["Bash", { command: "uv run pytest backend/tests 2>&1 | tee test-output.txt" }, null],
  ["Bash", { command: "git diff origin/main...HEAD -- docs/ | tee $TEMP/d.txt" }, null],
  ["Bash", { command: "uv run ruff format backend" }, null],
  ["Bash", { command: "sed -i 's/a/b/' /c/Users/me/scratchpad/notes.txt" }, null],
  ["Bash", { command: "sed -i 's/a/b/' /tmp/x.txt && uv run pytest backend/tests" }, null],
  ["Bash", { command: 'grep -rn "write_text" backend/' }, null],
  ["Bash", { command: 'grep -rn "sed -i" docs/' }, null],
  ["Bash", { command: "rg -n writeFileSync scripts/" }, null],
  ["Bash", { command: `grep -rn "open(" backend/ | grep "'w'"` }, null],
  ["Bash", { command: 'git commit -m "Guard sed -i and tee edits of docs/ and backend/"' }, null],
  ["Bash", { command: `node -e "console.log(['a'].map(f=>'docs/'+f))"` }, null],
  // Agents never open PRs (sso-registration retro), however the command is spelled...
  ["Bash", { command: "npm run pr -- sso-registration" }, "deny"],
  ["Bash", { command: "git status && npm run pr" }, "deny"],
  ["Bash", { command: "npm run -s pr -- sso" }, "deny"],
  ["Bash", { command: "npm run --silent pr" }, "deny"],
  ["Bash", { command: "npm run-script pr" }, "deny"],
  ["Bash", { command: "npm run pr&& echo ok" }, "deny"],
  ["Bash", { command: "npm run pr|cat" }, "deny"],
  ["Bash", { command: "echo $(npm run pr)" }, "deny"],
  ["Bash", { command: "node scripts/open-pr.mjs x" }, "deny"],
  ["Bash", { command: "node --no-warnings scripts/open-pr.mjs x" }, "deny"],
  ["Bash", { command: 'gh pr create --title "x" --body y' }, "deny"],
  ["Bash", { command: "gh pr new" }, "deny"],
  ["Bash", { command: "gh -R o/r pr create" }, "deny"],
  ["Bash", { command: "GH_REPO=o/r gh pr create" }, "deny"],
  ["Bash", { command: "env GH_TOKEN=x gh pr create" }, "deny"],
  ["Bash", { command: "GH.EXE pr create" }, "deny"],
  ["PowerShell", { command: '& "C:\\Program Files\\GitHub CLI\\gh.exe" pr create -t x' }, "deny"],
  ["PowerShell", { command: "npm run pr;" }, "deny"],
  // ...while text that only mentions it runs
  ["Bash", { command: 'grep -rn "npm run pr" docs' }, null],
  ["Bash", { command: 'rg "npm run pr|gh pr create" docs' }, null],
  ["Bash", { command: 'grep -rn "npm run pr\\|gh pr create" docs' }, null],
  ["Bash", { command: 'grep -E "(gh pr create)" docs/PROCESS.md' }, null],
  ["Bash", { command: "echo 'see (gh pr create)'" }, null],
  ["Bash", { command: 'git commit -m "Tell the human to run npm run pr"' }, null],
  [
    "Bash",
    { command: 'git commit -m "retro: x\n\ngh pr create and npm run pr are denied."' },
    null,
  ],
  [
    "Bash",
    { command: "git commit -F - <<'EOF'\nretro: x\n\nnpm run pr is for humans.\nEOF" },
    null,
  ],
  ["Bash", { command: "npm run pretty" }, null],
  ["Bash", { command: "gh pr view 18" }, null],
  // Reading, searching and dependency commands stay silent
  ["Bash", { command: 'grep -rn "type: ignore" backend' }, null],
  ["Bash", { command: "grep -n noqa backend/x.py 2>/dev/null" }, null],
  ["Bash", { command: "cat pyproject.toml" }, null],
  ["Bash", { command: "uv add sqlalchemy" }, null],
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

// A regex that backtracks badly would stall every tool call (sso-registration retro review).
test("the guard decides a 50,000-character command quickly", () => {
  for (const filler of [";/", "a/", " -x y", "'a b' "]) {
    const command = `gh ${filler.repeat(Math.ceil(50_000 / filler.length))}`;
    const started = performance.now();
    evaluate({ tool_name: "Bash", tool_input: { command } }, P);
    const elapsed = performance.now() - started;
    assert.ok(elapsed < 250, `${JSON.stringify(filler)} took ${Math.round(elapsed)} ms`);
  }
});

// The guard only sees tools the hook matcher routes to it. A shell tool missing there bypasses every rule.
test("settings route every shell tool through the guard and deny push for each", () => {
  const settings = JSON.parse(readFileSync(".claude/settings.json", "utf8"));
  const matchers = settings.hooks.PreToolUse.map((entry) => entry.matcher.split("|"));
  const guarded = matchers.find((names) => names.includes("Read")) ?? [];

  for (const tool of SHELL_TOOLS) {
    assert.ok(guarded.includes(tool), `${tool} is not routed through the guard`);
    assert.ok(settings.permissions.deny.includes(`${tool}(git push *)`), `${tool} can push`);
    const prRules = ["npm run pr", "npm run pr *", "gh pr create", "gh pr create *"];
    for (const rule of [...prRules, "gh pr new", "gh pr new *"]) {
      assert.ok(settings.permissions.deny.includes(`${tool}(${rule})`), `${tool} can open a PR`);
    }
  }
});
