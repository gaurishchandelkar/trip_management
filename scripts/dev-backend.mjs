// Starts the dev backend (`npm run dev:backend`). When the git-ignored env file exists, uv
// loads it, so the Google client ID and secret can live there (docs/SECURITY_GUIDELINES.md:
// secrets live in .env files). uv refuses a missing --env-file, so the flag is only passed
// when there is one. Variables already set in the shell win over the file.
// Agents never read the file: only the backend process does, when a human runs this.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { pathToFileURL } from "node:url";

export const ENV_FILE = ".env";
const SERVER = ["-m", "uvicorn", "backend.main:app", "--reload", "--reload-dir", "backend"];

export function backendArgs(envFileExists) {
  return ["run", ...(envFileExists ? ["--env-file", ENV_FILE] : []), ...SERVER];
}

function main() {
  const child = spawn("uv", backendArgs(existsSync(ENV_FILE)), { stdio: "inherit" });
  child.on("error", (error) => {
    console.error(`Couldn't start uv: ${error.message}`);
    process.exitCode = 1;
  });
  child.on("exit", (code) => {
    process.exitCode = code ?? 1;
  });
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) main();
