// Opens a PR from the description in .git/PR_BODY_<name>.md, written by /ship, /retro or a small
// change (docs/PROCESS.md). For the human to run. Usage: npm run pr -- <name>
// One short command, because a long `gh pr create` line wraps in a terminal and the break ends up
// in the PR title, and gh may be installed but missing from Git Bash's PATH
// (docs/HARNESS_LOG.md, app-shell-and-design-system retro).
// When the branch changes the UI, the e2e captures (e2e/test_screenshots.py) are attached below
// the body: the screens the code produces, not screenshots an agent took by hand.
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { EXPECTED, summarize } from "./screenshot-summary.mjs";

const NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SCREENSHOTS = "test-results/screenshots";
// Changes that can alter what the captured screens look like.
const UI_PATHS = ["frontend", "e2e/test_screenshots.py"];

export function changesUi(changedFiles) {
  return changedFiles.some((file) =>
    UI_PATHS.some((path) => file === path || file.startsWith(`${path}/`)),
  );
}

/**
 * `--attach` arguments for the 20 captures, in screen order with alt text such as
 * "sign in, dark, 360 px". Refuses a partial set, or one older than the branch's last UI change.
 */
export function screenshotAttachments(dir, files, lastUiChangeMs) {
  const { missing, unexpected } = summarize(files.map((file) => file.name));
  if (missing.length > 0 || unexpected.length > 0)
    return {
      error: `${dir} doesn't hold exactly the ${String(EXPECTED.length)} captures. Run: npm run check -- functional`,
    };
  if (files.some((file) => file.mtimeMs < lastUiChangeMs))
    return {
      error: `${dir} is older than this branch's last UI change. Run: npm run check -- functional`,
    };
  const args = EXPECTED.flatMap((name) => {
    const [, screen, theme, width] = /^(.+)-(light|dark)-(\d+)\.png$/.exec(name) ?? [];
    return ["--attach", `${dir}/${name}#${screen.replaceAll("-", " ")}, ${theme}, ${width} px`];
  });
  return { args };
}

function git(args) {
  return spawnSync("git", args, { encoding: "utf8" }).stdout.trim();
}

export function specTitle(spec) {
  return /^# Spec: (.+)$/m.exec(spec)?.[1].trim() ?? null;
}

const BODY_HEADING = /^# (\S.*?)[ \t]*(?:\r?\n|$)(?:[ \t]*\r?\n)*/;
// PowerShell 5's `Set-Content -Encoding utf8` starts a file with a byte order mark.
const BOM = 0xfeff;

/**
 * The PR's title and body. A body that starts with a "# <title>" line (a retro or a small fix)
 * takes that title, and the line is dropped from the body. Otherwise the spec's title is used.
 */
export function titleAndBody(spec, written) {
  const body = written.codePointAt(0) === BOM ? written.slice(1) : written;
  const heading = BODY_HEADING.exec(body);
  if (heading !== null) return { title: heading[1], body: body.slice(heading[0].length) };
  const title = spec === null ? null : specTitle(spec);
  return title === null ? null : { title, body };
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
  if (!NAME.test(name)) return fail("Usage: npm run pr -- <name>, such as app-shell");

  const specPath = `docs/specs/${name}.md`;
  const bodyPath = `.git/PR_BODY_${name}.md`;
  if (!existsSync(bodyPath))
    return fail(
      `No PR body at ${bodyPath}. Run /ship ${name}, or for a small change write it as docs/PROCESS.md says.`,
    );
  const spec = existsSync(specPath) ? readFileSync(specPath, "utf8") : null;
  const pr = titleAndBody(spec, readFileSync(bodyPath, "utf8"));
  if (pr === null)
    return fail(
      spec === null
        ? `No spec at ${specPath}, so ${bodyPath} must start with a "# <title>" line.`
        : `${specPath} has no "# Spec: <title>" heading.`,
    );

  const gh = findGh();
  if (gh === undefined)
    return fail("GitHub CLI (gh) not found. Install it: https://cli.github.com");

  let attachments = [];
  if (changesUi(git(["diff", "--name-only", "main...HEAD"]).split("\n"))) {
    const lastUiChange = Number(
      git(["log", "-1", "--format=%ct", "main..HEAD", "--", ...UI_PATHS]),
    );
    const files = existsSync(SCREENSHOTS)
      ? readdirSync(SCREENSHOTS).map((file) => ({
          name: file,
          mtimeMs: statSync(`${SCREENSHOTS}/${file}`).mtimeMs,
        }))
      : [];
    const { args, error } = screenshotAttachments(SCREENSHOTS, files, lastUiChange * 1000);
    if (error !== undefined) return fail(error);
    attachments = args;
  }
  // A file, not --body: Windows caps a whole command line at 32,767 characters.
  const sentBody = `.git/PR_BODY_${name}.sent.md`;
  writeFileSync(sentBody, pr.body);
  const args = ["pr", "create", "--title", pr.title, "--body-file", sentBody, ...attachments];
  const { status, error } = spawnSync(gh, args, { stdio: "inherit" });
  rmSync(sentBody, { force: true });
  if (error !== undefined) return fail(`Couldn't run gh: ${error.message}`);
  process.exitCode = status ?? 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) main();
