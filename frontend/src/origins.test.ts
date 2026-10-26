// @vitest-environment node
// Reads files from disk, so it needs Node rather than jsdom.
import { globSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Everything the browser loads is served by the app itself: fonts and icons are bundled, and
// pages talk only to /api. The E2E traffic check catches third-party requests on the screens
// the tests open; this catches them in source, before any screen does.
const FRONTEND = fileURLToPath(new URL("..", import.meta.url));
const SOURCES = globSync("{index.html,public/**/*,src/**/*.{ts,tsx,css}}", { cwd: FRONTEND })
  .map((path) => path.replaceAll("\\", "/"))
  .filter((path) => !/\.test\.tsx?$/.test(path));

// The SVG namespace is an identifier, never fetched.
const ALLOWED = new Set(["http://www.w3.org/2000/svg"]);

function externalUrls(text: string): string[] {
  return Array.from(
    text.matchAll(/(?:https?:)?\/\/[\w.-]+\.[a-z]{2,}[^\s"'`)<>]*/gi),
    ([url]) => url,
  ).filter((url) => !ALLOWED.has(url));
}

describe("third-party origins", () => {
  it("found the frontend sources to scan", () => {
    expect(SOURCES).toEqual(
      expect.arrayContaining(["index.html", "src/main.tsx", "src/theme/tokens.css"]),
    );
  });

  it.each(SOURCES)("%s loads nothing from another origin", (path) => {
    expect(externalUrls(readFileSync(`${FRONTEND}/${path}`, "utf8"))).toEqual([]);
  });

  it("externalUrls finds absolute and protocol-relative URLs, and skips the SVG namespace", () => {
    const text = [
      '<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet" />',
      "@import url(//cdn.example.com/x.css);",
      '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
      'fetch("/api/me")',
    ].join("\n");

    expect(externalUrls(text)).toEqual([
      "https://fonts.googleapis.com/css2?family=Inter",
      "//cdn.example.com/x.css",
    ]);
  });
});
