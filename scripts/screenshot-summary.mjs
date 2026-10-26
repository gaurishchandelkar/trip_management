// Prints the "UI screenshots" section of the CI job summary, and checks the set is complete
// (docs/specs/ci-screenshot-artifacts.md). Usage: node scripts/screenshot-summary.mjs <dir>
// Exits 1 when a screenshot is missing or unexpected, so a partial set never looks complete.
// The lists match e2e/test_screenshots.py, checked by scripts/screenshot-summary.test.mjs.
import { existsSync, readdirSync } from "node:fs";
import { pathToFileURL } from "node:url";

export const SCREENS = ["sign-in", "home", "new-group-dialog", "group", "not-found"];
export const THEMES = ["light", "dark"];
export const WIDTHS = [360, 1280];

const VARIANTS = THEMES.flatMap((theme) => WIDTHS.map((width) => `${theme}-${String(width)}`));
export const EXPECTED = SCREENS.flatMap((screen) => VARIANTS.map((v) => `${screen}-${v}.png`));

export function summarize(files) {
  const present = new Set(files);
  const missing = EXPECTED.filter((file) => !present.has(file));
  const unexpected = files.filter((file) => !EXPECTED.includes(file)).sort();
  const cell = (screen, variant) =>
    present.has(`${screen}-${variant}.png`) ? "yes" : "**missing**";
  const lines = [
    "## UI screenshots",
    "",
    `${String(EXPECTED.length - missing.length)} of ${String(EXPECTED.length)} screenshots, in this run's \`ui-screenshots\` artifact (run Summary, Artifacts).`,
    "",
    `| Screen | ${VARIANTS.join(" | ")} |`,
    `|---|${VARIANTS.map(() => "---").join("|")}|`,
    ...SCREENS.map(
      (screen) => `| ${screen} | ${VARIANTS.map((v) => cell(screen, v)).join(" | ")} |`,
    ),
  ];
  if (unexpected.length > 0)
    lines.push("", `Unexpected files: ${unexpected.map((file) => `\`${file}\``).join(", ")}`);
  return {
    markdown: `${lines.join("\n")}\n`,
    missing,
    unexpected,
    ok: missing.length === 0 && unexpected.length === 0,
  };
}

function main() {
  const dir = process.argv[2] ?? "";
  const result = summarize(dir !== "" && existsSync(dir) ? readdirSync(dir) : []);
  process.stdout.write(result.markdown);
  if (!result.ok) {
    console.error(
      `UI screenshots incomplete. Missing: ${result.missing.join(", ") || "none"}. ` +
        `Unexpected: ${result.unexpected.join(", ") || "none"}.`,
    );
    process.exitCode = 1;
  }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) main();
