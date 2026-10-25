// PreToolUse guard: enforces the hard lines in docs/RULES.md for agent tool calls.
// It's a seatbelt, not a sandbox: CI and code review remain the backstop.
import path from "node:path";
import { pathToFileURL } from "node:url";

const ENV_FILE = /(?:^|[\s"'=<>/\\:])\.env(?:\.(?!example\b)[\w.-]+)?(?=$|[\s"'<>;|&)])/;

// Every shell tool gets the same rules: on Windows, PowerShell is as able to push as Bash.
export const SHELL_TOOLS = ["Bash", "PowerShell"];

const SHELL_RULES = [
  [/\bgit\s+(?:-[cC]\s+\S+\s+)*push\b/, "Agents never push. Ask a human to push."],
  [/--no-verify\b|\bgit\s+commit\b.*\s-n(?:\s|$)/, "Never skip git hooks. Fix the failing check."],
  [
    /\bLEFTHOOK=(?:0|false)\b|\$env:LEFTHOOK\s*=\s*["']?(?:0|false)\b|\blefthook\s+uninstall\b|core\.hooksPath/i,
    "Never disable git hooks.",
  ],
  [ENV_FILE, "Never access .env files. Ask a human to set secrets."],
];

const SUPPRESSION =
  /#\s*noqa|type:\s*ignore|pyright:\s*ignore|eslint-disable|@ts-(?:ignore|expect-error|nocheck)|pragma:\s*allowlist/;

const THRESHOLD = /(?:fail[_-]under|"?(?:lines|branches|functions|statements)"?)\s*[=:]?\s*(\d+)/g;
const THRESHOLD_FILES = /^(?:pyproject\.toml|package\.json|frontend\/vite\.config\.ts)$/;
const MIN_COVERAGE = 80;

// Rule exclusions and weaker type checking disable safeguards: a human decides.
const RULE_EXCLUSION =
  /per-file-ignores|^\s*(?:extend-)?(?:ignore|exclude|extend-exclude)\s*=|^\s*"[^"]+"\s*=\s*\[\s*"[A-Z]+\d*"|typeCheckingMode|^\s*report\w+\s*=\s*(?:false|"none")/m;

const PROTECTED =
  /^(?:\.claude\/|\.github\/|lefthook\.yml$|eslint\.config\.js$|\.secrets\.baseline$|AGENTS\.md$|CLAUDE\.md$|docs\/(?:RULES|SECURITY_GUIDELINES)\.md$)/;
const PROTECTED_IN_SHELL =
  /(?:>|\btee\b|\bsed\s+-i\b|\bmv\b|\bcp\b|\brm\b|\b(?:Set|Add|Clear)-Content\b|\bOut-File\b|\b(?:Copy|Move|Remove|New|Rename)-Item\b)[^|;&]*(?:\.claude[/\\]|\.github[/\\]|lefthook\.yml|eslint\.config\.js|\.secrets\.baseline)/i;

function relative(filePath, projectDir) {
  return path.relative(projectDir, path.resolve(projectDir, filePath)).split(path.sep).join("/");
}

function newContent(toolName, input) {
  if (toolName === "Write") return input.content ?? "";
  if (toolName === "Edit") return input.new_string ?? "";
  if (toolName === "MultiEdit") return (input.edits ?? []).map((e) => e.new_string).join("\n");
  return "";
}

export function evaluate({ tool_name: toolName, tool_input: input = {} }, projectDir) {
  if (SHELL_TOOLS.includes(toolName)) {
    const command = input.command ?? "";
    for (const [pattern, reason] of SHELL_RULES) {
      if (pattern.test(command)) return { decision: "deny", reason };
    }
    if (PROTECTED_IN_SHELL.test(command)) {
      return { decision: "ask", reason: "Shell write to harness files needs human approval." };
    }
    return null;
  }

  if (!input.file_path) return null;
  const file = relative(input.file_path, projectDir);
  if (/(?:^|\/)\.env(?:\.(?!example$).+)?$/.test(file)) {
    return { decision: "deny", reason: "Never access .env files. Ask a human to set secrets." };
  }
  if (toolName === "Read") return null;

  const content = newContent(toolName, input);
  if (!file.endsWith(".md") && !file.startsWith(".claude/hooks/") && SUPPRESSION.test(content)) {
    return {
      decision: "deny",
      reason:
        "Suppression comments are not allowed (docs/CODING_GUIDELINES.md). Fix the issue or ask.",
    };
  }
  if (THRESHOLD_FILES.test(file)) {
    for (const [, value] of content.matchAll(THRESHOLD)) {
      if (Number(value) < MIN_COVERAGE) {
        return { decision: "deny", reason: `Coverage thresholds must stay >= ${MIN_COVERAGE}%.` };
      }
    }
  }
  if (file === "pyproject.toml" && RULE_EXCLUSION.test(content)) {
    return { decision: "ask", reason: "Rule exclusions need human approval (docs/RULES.md)." };
  }
  if (PROTECTED.test(file)) {
    return {
      decision: "ask",
      reason: `${file} is part of the harness. A human must approve changes.`,
    };
  }
  return null;
}

async function main() {
  let raw = "";
  for await (const chunk of process.stdin) raw += chunk;
  const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
  const result = evaluate(JSON.parse(raw), projectDir);
  if (!result) return;
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: result.decision,
        permissionDecisionReason: result.reason,
      },
    }),
  );
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) await main();
