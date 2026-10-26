// Opens the PR that /ship prepared. For the human to run: agents never push or open PRs
// (docs/RULES.md). Usage: npm run pr -- <spec-name>
// One short command, because a long `gh pr create` line wraps in a terminal and the break ends up
// in the PR title, and gh may be installed but missing from Git Bash's PATH
// (docs/HARNESS_LOG.md, app-shell-and-design-system retro).
// Screenshots that /ship saved to .playwright-mcp/pr-<spec-name>/ are attached below the body.
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const SPEC_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const MEDIA = /\.(?:png|jpe?g|gif|webp|mp4)$/i;

/** `--attach` arguments for each image in the folder, in name order, with alt text from the name. */
export function attachArgs(dir, files) {
  return files
    .filter((file) => MEDIA.test(file))
    .sort((a, b) => a.localeCompare(b, "en", { numeric: true }))
    .flatMap((file) => {
      const alt = file.replace(MEDIA, "").replace(/^\d+-/, "").replaceAll("-", " ");
      return ["--attach", `${dir}/${file}#${alt}`];
    });
}

export function specTitle(spec) {
  return /^# Spec: (.+)$/m.exec(spec)?.[1].trim() ?? null;
}

export function ghCandidates(platform, env) {
  if (platform !== "win32") return ["gh"];
  const dirs = [env.ProgramFiles, env.LOCALAPPDATA && `${env.LOCALAPPDATA}\\Programs`];
  return ["gh", ...dirs.filter(Boolean).map((dir) => `${dir}\\GitHub CLI\\gh.exe`)];
}

function findGh() {
  return ghCandidates(process.platform, process.env).find(
    (gh) => spawnSync(gh, ["--version"], { stdio: "ignore" }).status === 0,
  );
}

function fail(message) {
  console.error(message);
  process.exitCode = 1;
}

function main() {
  const name = process.argv[2] ?? "";
  if (!SPEC_NAME.test(name)) return fail("Usage: npm run pr -- <spec-name>, such as app-shell");

  const specPath = `docs/specs/${name}.md`;
  const bodyPath = `.git/PR_BODY_${name}.md`;
  if (!existsSync(specPath)) return fail(`No spec at ${specPath}.`);
  if (!existsSync(bodyPath)) return fail(`No PR body at ${bodyPath}. Run /ship ${name} first.`);
  const title = specTitle(readFileSync(specPath, "utf8"));
  if (title === null) return fail(`${specPath} has no "# Spec: <title>" heading.`);

  const gh = findGh();
  if (gh === undefined)
    return fail("GitHub CLI (gh) not found. Install it: https://cli.github.com");

  const screenshots = `.playwright-mcp/pr-${name}`;
  const attachments = existsSync(screenshots)
    ? attachArgs(screenshots, readdirSync(screenshots))
    : [];
  const args = ["pr", "create", "--title", title, "--body-file", bodyPath, ...attachments];
  const { status } = spawnSync(gh, args, { stdio: "inherit" });
  process.exitCode = status ?? 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) main();
