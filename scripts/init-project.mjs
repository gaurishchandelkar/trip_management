// Turns a fresh copy of this template into your project. Run once, by a human, before the first push.
// Usage: node scripts/init-project.mjs --name my-app --owner your-github-handle
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: { name: { type: "string" }, owner: { type: "string" } },
});
const { name, owner } = values;

if (!name || !/^[a-z][a-z0-9-]*$/.test(name) || !owner || !/^[\w.-]+(\/[\w.-]+)?$/.test(owner)) {
  console.error(
    "Usage: node scripts/init-project.mjs --name <kebab-case-name> --owner <github user or org/team>",
  );
  process.exit(2);
}

const title = name
  .split("-")
  .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
  .join(" ");

const replacements = {
  "package.json": [['"name": "hyper-harness"', `"name": "${name}"`]],
  "package-lock.json": [['"name": "hyper-harness"', `"name": "${name}"`]],
  "pyproject.toml": [['name = "hyper-harness"', `name = "${name}"`]],
  "uv.lock": [['name = "hyper-harness"', `name = "${name}"`]],
  "README.md": [["# Hyper Harness", `# ${title}`]],
  "frontend/index.html": [["<title>Hyper Harness</title>", `<title>${title}</title>`]],
  "backend/main.py": [['FastAPI(title="Hyper Harness")', `FastAPI(title="${title}")`]],
  ".github/CODEOWNERS": [["@OWNER", `@${owner}`]],
};

for (const [file, pairs] of Object.entries(replacements)) {
  let text = readFileSync(file, "utf8");
  for (const [from, to] of pairs) text = text.replaceAll(from, to);
  writeFileSync(file, text);
}

// The template's own build plan is history, not your project's plan.
if (existsSync("docs/PLAN.md")) rmSync("docs/PLAN.md");

console.log(`Initialised "${title}" (${name}), owned by @${owner}.

Next:
  uv sync && npm install
  npm run check
  git add -A && git commit -m "Initialise ${name} from the hyper-harness template"
  # create the GitHub repo, push, wait for the first CI run, then (as an admin):
  node scripts/protect-branch.mjs   # add --solo if you're the only maintainer`);
