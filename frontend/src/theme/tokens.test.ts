// @vitest-environment node
// Reads files and does arithmetic, so it needs Node's URL rather than jsdom's.
import { globSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Read from disk: vitest replaces imported CSS, even `?raw`, with an empty string.
const SRC = fileURLToPath(new URL("..", import.meta.url));
const stylesheets = Object.fromEntries(
  globSync("**/*.css", { cwd: SRC }).map((path) => [
    path.replaceAll("\\", "/"),
    readFileSync(`${SRC}/${path}`, "utf8"),
  ]),
);
const tokensCss = stylesheets["theme/tokens.css"] ?? "";

type Tokens = Map<string, string>;

function declarations(block: string): Tokens {
  return new Map(
    Array.from(block.matchAll(/(--[\w-]+):\s*([^;]+);/g), (match) => [
      match[1] ?? "",
      (match[2] ?? "").trim(),
    ]),
  );
}

const [lightBlock = "", darkBlock = ""] = tokensCss.split("@media (prefers-color-scheme: dark)");
const light = declarations(lightBlock);
// The dark block overrides the light one: anything it leaves out is inherited.
const dark = new Map([...light, ...declarations(darkBlock)]);

function luminance(hex: string): number {
  const value = Number.parseInt(hex.slice(1), 16);
  const channel = (shift: number) => {
    const c = ((value >> shift) & 0xff) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(16) + 0.7152 * channel(8) + 0.0722 * channel(0);
}

function contrast(tokens: Tokens, foreground: string, background: string): number {
  const colours = [foreground, background].map((name) => {
    const value = tokens.get(name);
    if (value === undefined || !/^#[0-9a-f]{6}$/i.test(value))
      throw new Error(`${name} must be a 6-digit hex colour, not ${String(value)}`);
    return luminance(value);
  });
  const [lighter = 0, darker = 0] = colours.sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

const TEXT = 4.5;
const NON_TEXT = 3;

// Every colour pair that carries meaning: text on its surface, input borders and the focus ring.
const PAIRS: [foreground: string, background: string, minimum: number][] = [
  ["--color-text", "--color-bg", TEXT],
  ["--color-text", "--color-surface", TEXT],
  ["--color-text", "--color-surface-sunken", TEXT],
  ["--color-text-muted", "--color-bg", TEXT],
  ["--color-text-muted", "--color-surface", TEXT],
  ["--color-link", "--color-surface", TEXT],
  ["--color-link", "--color-bg", TEXT],
  ["--color-on-primary", "--color-primary", TEXT],
  ["--color-on-primary", "--color-primary-hover", TEXT],
  ["--color-on-danger", "--color-danger", TEXT],
  ["--color-on-danger", "--color-danger-hover", TEXT],
  ["--color-success-text", "--color-success-bg", TEXT],
  ["--color-danger-text", "--color-danger-bg", TEXT],
  ["--color-badge-owner-text", "--color-badge-owner-bg", TEXT],
  ["--color-badge-member-text", "--color-badge-member-bg", TEXT],
  ["--color-badge-pending-text", "--color-badge-pending-bg", TEXT],
  ["--color-avatar-text", "--color-avatar-bg", TEXT],
  ["--color-border-strong", "--color-surface", NON_TEXT],
  ["--color-danger", "--color-surface", NON_TEXT],
  ["--color-focus", "--color-surface", NON_TEXT],
  ["--color-focus", "--color-bg", NON_TEXT],
  ["--color-brand", "--color-surface", NON_TEXT],
  ["--color-on-brand", "--color-brand", NON_TEXT],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme contrast", (_theme, tokens) => {
  it.each(PAIRS)("%s on %s is at least %d:1", (foreground, background, minimum) => {
    expect(contrast(tokens, foreground, background)).toBeGreaterThanOrEqual(minimum);
  });
});

describe("raw colours", () => {
  it("found the stylesheets to scan, with their contents", () => {
    expect(Object.keys(stylesheets)).toEqual(
      expect.arrayContaining(["theme/tokens.css", "theme/base.css", "ui/ui.css"]),
    );
    for (const css of Object.values(stylesheets)) expect(css.length).toBeGreaterThan(0);
    expect(light.size).toBeGreaterThan(20);
  });

  it.each(Object.entries(stylesheets).filter(([path]) => path !== "theme/tokens.css"))(
    "%s uses tokens, never raw colours",
    (_path, css) => {
      expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(/i);
    },
  );
});
