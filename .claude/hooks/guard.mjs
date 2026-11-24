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

// A human opens PRs (docs/PROCESS.md). Matched in commandText where a command starts, after
// optional `VAR=x` or `env`, so a grep pattern or commit message that only mentions it runs.
const OPENS_PR = new RegExp(
  String.raw`(?:^|[;&|({` +
    "`" +
    String.raw`]\s*|\n\s*)(?:\w+=\S*\s+)*(?:env\s+(?:\w+=\S*\s+)*)?` +
    String.raw`(?:npm(?:\.cmd)?(?:\s+-\S+)*\s+(?:run|run-script)(?:\s+-\S+)*\s+pr(?![\w:.-])` +
    String.raw`|node(?:\.exe)?(?:\s+-\S+)*\s+\S*open-pr\.mjs` +
    String.raw`|(?:[^\s/\\;&|]*[/\\])*gh(?:\.exe)?(?:\s+-\S+(?:\s+[^-\s]\S*)?)*\s+pr\s+(?:create|new)\b)`,
  "i",
);

/**
 * What the shell will run: heredoc bodies dropped, and quoted strings that hold whitespace
 * (commit messages, grep patterns) emptied. A quoted path to gh is kept as `gh`, and `|;&`
 * inside other quotes (`'s|a|b|'`) no longer split commands.
 */
export function commandText(command) {
  const kept = [];
  let terminator = null;
  for (const line of command.split("\n")) {
    if (terminator !== null) {
      if (line.trim() === terminator) terminator = null;
      continue;
    }
    kept.push(line);
    terminator = /<<-?\s*(["']?)([\w-]+)\1/.exec(line)?.[2] ?? null;
  }
  return kept.join("\n").replace(/"[^"]*"|'[^']*'/g, (quoted) => {
    const inner = quoted.slice(1, -1);
    if (/(?:^|[/\\])gh(?:\.exe)?$/i.test(inner)) return "gh";
    return /\s/.test(inner) ? '""' : quoted.replace(/[|;&]/g, "_");
  });
}

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

// Shell writes skip the content checks below, so they ask when they could disable one:
// a suppression comment, or a write to a file that holds thresholds or rule exclusions.
const SHELL_WRITE =
  /(?<![\d&])>|\btee\b|\bsed\s+-i\b|\bopen\([^)]*["'][wa+]|\bwrite_text\b|\bwriteFileSync\b|\b(?:Set|Add)-Content\b|\bOut-File\b/;
const CHECK_CONFIG = /\b(?:pyproject\.toml|package\.json|vite\.config\.ts)\b/;

// docs/CODING_GUIDELINES.md rule 6: source, tests and docs are edited with Edit or Write, which
// the content checks below can see (sso-registration retro). Each rule looks at what a write
// targets, so reading, searching and test runs that only name those paths stay silent. A `cd`
// into a folder first, or a path held in a variable, still gets through: it's a seatbelt.
const SOURCE = String.raw`(?<![\w.-])(?:(?:backend|frontend|e2e|scripts|docs)[/\\]|(?:README|AGENTS|CLAUDE)\.md\b)`;
const TARGET = String.raw`["']?[^\s"'|;&<>]*?${SOURCE}`;
const SOURCE_PATH = new RegExp(SOURCE);
const SHELL_EDITS = [
  new RegExp(String.raw`\bsed\b(?=[^|;&\n]*\s(?:-[A-Za-z]*i|--in-place)\b)[^|;&\n]*${SOURCE}`),
  new RegExp(String.raw`\bperl\b(?=[^|;&\n]*\s-[A-Za-z]*i)[^|;&\n]*${SOURCE}`),
  new RegExp(String.raw`\btee\b(?:\s+-\S+)*\s+${TARGET}`),
  new RegExp(String.raw`(?<![=\-<])[12&]?>>?\s*${TARGET}`),
  new RegExp(
    String.raw`(?:^|[;|&{(]\s*|\n\s*)(?:Set-Content|Add-Content|Out-File)\b[^|;&\n]*${SOURCE}`,
    "i",
  ),
];
// Script writes count only when an interpreter runs (or the tool is PowerShell), so a grep
// for `write_text` doesn't ask. Their paths may sit in a heredoc body, so the raw command is read.
const SCRIPT_WRITE =
  /\bwrite_(?:text|bytes)\b|\bopen\([^)]*["'][wax]\+?["']|\b(?:writeFile|writeFileSync|appendFile|appendFileSync)\b|\bWriteAll(?:Text|Bytes|Lines)\b/;
const INTERPRETER = /(?:^|[\s;&|(])(?:python3?|py|node|deno|pwsh|powershell)(?:\.exe)?(?=\s|$)/m;

function editsSourceInShell(toolName, command) {
  const text = commandText(command);
  if (SHELL_EDITS.some((pattern) => pattern.test(text))) return true;
  const interpreter = toolName === "PowerShell" || INTERPRETER.test(text);
  return interpreter && SCRIPT_WRITE.test(command) && SOURCE_PATH.test(command);
}

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
    if (OPENS_PR.test(commandText(command))) {
      return {
        decision: "deny",
        reason: "Agents never open PRs. Give the human `npm run pr -- <name>`.",
      };
    }
    if (PROTECTED_IN_SHELL.test(command)) {
      return { decision: "ask", reason: "Shell write to harness files needs human approval." };
    }
    if (SHELL_WRITE.test(command) && (SUPPRESSION.test(command) || CHECK_CONFIG.test(command))) {
      return {
        decision: "ask",
        reason:
          "Shell writes skip the guard's content checks. Use Edit or Write for check config and suppressions, or ask.",
      };
    }
    if (editsSourceInShell(toolName, command)) {
      return {
        decision: "ask",
        reason:
          "Edit source, tests and docs with Edit or Write, so the guard can check them (docs/CODING_GUIDELINES.md rule 6).",
      };
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
