// PostToolUse: formats each file the agent edits so diffs stay clean and pre-commit stays fast.
import { spawnSync } from "node:child_process";
import path from "node:path";

const PRETTIER_EXTENSIONS = new Set([
  ".ts",
  ".tsx",
  ".js",
  ".mjs",
  ".json",
  ".css",
  ".html",
  ".yml",
]);

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const filePath = JSON.parse(raw).tool_input?.file_path;

const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
const relativePath = filePath ? path.relative(projectDir, filePath) : "..";
const insideProject = !relativePath.startsWith("..") && !path.isAbsolute(relativePath);

if (insideProject) {
  const extension = path.extname(filePath);
  if (extension === ".py") {
    spawnSync("uv", ["run", "ruff", "format", filePath], { cwd: projectDir, stdio: "ignore" });
  } else if (PRETTIER_EXTENSIONS.has(extension)) {
    const prettier = path.join(projectDir, "node_modules", "prettier", "bin", "prettier.cjs");
    spawnSync(process.execPath, [prettier, "--write", "--ignore-unknown", filePath], {
      cwd: projectDir,
      stdio: "ignore",
    });
  }
}
