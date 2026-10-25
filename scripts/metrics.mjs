// Time-to-validated-outcome metrics from git history and the harness log (docs/METRICS.md).
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

function git(...args) {
  return execFileSync("git", args, { encoding: "utf8" }).trim();
}

function commitDates(...args) {
  const out = git("log", "--format=%aI", ...args);
  return out ? out.split("\n").map((date) => new Date(date)) : [];
}

function earliest(dates) {
  return dates.length > 0 ? new Date(Math.min(...dates.map(Number))) : null;
}

export function summarise({ specAdded, planApproved, planDone, subjects, specEdits }, name) {
  const phases = subjects.filter((s) => s.startsWith(`${name}: phase `)).length;
  const fixes = subjects.filter((s) => s.startsWith(`${name}: fix`)).length;
  const hours = specAdded && planDone ? (planDone - specAdded) / 3_600_000 : null;
  return {
    feature: name,
    "spec→done (h)": hours === null ? "in progress" : hours.toFixed(1),
    phases,
    "fix-ups": fixes,
    "first-pass rate":
      phases > 0 ? `${String(Math.round((100 * Math.max(phases - fixes, 0)) / phases))}%` : "-",
    "spec rework": planApproved
      ? specEdits.filter((edit) => edit.date > planApproved && !edit.progressOnly).length
      : 0,
  };
}

// Ticking acceptance criteria and moving the Status line at "done" are progress, not rework.
export function isProgressOnly(diff) {
  const changed = diff.split("\n").filter((line) => /^[+-](?![+-]{2})/.test(line));
  const normalise = (line) =>
    line
      .slice(1)
      .replace(/^(\s*- )\[[ xX]\]/, "$1[ ]")
      .replace(/^Status: .*/, "Status:");
  const removed = changed
    .filter((line) => line.startsWith("-"))
    .map(normalise)
    .sort();
  const added = changed
    .filter((line) => line.startsWith("+"))
    .map(normalise)
    .sort();
  return removed.length === added.length && removed.every((line, i) => line === added[i]);
}

export function countSignals(log) {
  const entries = log.match(/^## \d{4}-\d{2}-\d{2}/gm) ?? [];
  const escaped = log.match(/^- Signal: escaped defect\s*$/gm) ?? [];
  return { entries: entries.length, escapedDefects: escaped.length };
}

function featureData(name) {
  const spec = `docs/specs/${name}.md`;
  const plan = `docs/plans/PLAN_${name}.md`;
  return {
    specAdded: earliest(commitDates("--diff-filter=A", "--", spec)),
    planApproved: earliest(commitDates("-G", "Status: \\*\\*Approved\\*\\*", "--", plan)),
    planDone: earliest(commitDates("-G", "Status: \\*\\*Done\\*\\*", "--", plan)),
    subjects: git("log", "--format=%s").split("\n"),
    specEdits: specEdits(spec),
  };
}

function specEdits(spec) {
  const out = git("log", "--format=%H %aI", "--", spec);
  if (!out) return [];
  return out.split("\n").map((line) => {
    const [sha, date] = line.split(" ");
    return {
      date: new Date(date),
      progressOnly: isProgressOnly(git("show", "--format=", "--unified=0", sha, "--", spec)),
    };
  });
}

function countMatches(dir, pattern, filter) {
  if (!existsSync(dir)) return 0;
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter(filter)
    .reduce(
      (n, file) => n + (readFileSync(`${dir}/${file}`, "utf8").match(pattern)?.length ?? 0),
      0,
    );
}

function main() {
  const names = existsSync("docs/specs")
    ? readdirSync("docs/specs")
        .filter((f) => f.endsWith(".md"))
        .map((f) => f.slice(0, -3))
    : [];
  console.log("\nFeatures (time to validated outcome)");
  if (names.length > 0) console.table(names.map((name) => summarise(featureData(name), name)));
  else console.log("  No specs yet. Start with /spec.");

  const signals = countSignals(
    existsSync("docs/HARNESS_LOG.md") ? readFileSync("docs/HARNESS_LOG.md", "utf8") : "",
  );
  console.log("\nHarness growth");
  console.table({
    "python tests": countMatches("backend/tests", /^def test_/gm, (f) => f.endsWith(".py")),
    "frontend tests": countMatches("frontend/src", /^\s*it\(/gm, (f) => /\.test\.tsx?$/.test(f)),
    "e2e tests": countMatches("e2e", /^def test_/gm, (f) => f.endsWith(".py")),
    "harness tests": countMatches(".claude/hooks", /^\s*\[/gm, (f) => f.endsWith(".test.mjs")),
    skills: existsSync(".claude/skills") ? readdirSync(".claude/skills").length : 0,
    "harness log entries": signals.entries,
    "escaped defects": signals.escapedDefects,
  });
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) main();
