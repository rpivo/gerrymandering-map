import { describe, expect, it } from "vitest";

import css from "../styles/global.css?raw";

/** Read the custom properties declared in the first `:root { ... }` block after `start`. */
function tokens(start: number): Record<string, string> {
  const open = css.indexOf(":root {", start);
  const body = css.slice(open, css.indexOf("}", open));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
}

/** WCAG relative luminance of a #rrggbb color. */
function luminance(hex: string): number {
  const [r = 0, g = 0, b = 0] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio between two #rrggbb colors, from 1 to 21. */
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const light = tokens(0);
const dark = { ...light, ...tokens(css.indexOf("prefers-color-scheme: dark")) };
const bands = ["very-compact", "compact", "middle", "irregular", "very-irregular"];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s mode colors", (_mode, t) => {
  it("found every token it checks", () => {
    // Anchor: a parsing slip that found no tokens would make the checks below pass vacuously.
    const names = ["bg", "surface", "text", "text-muted", "accent", ...bands.flatMap((b) => [`band-${b}`, `on-band-${b}`])];
    expect(names.filter((n) => !t[n])).toEqual([]);
  });

  it.each(bands)("score badge text on the %s band reaches 4.5:1", (band) => {
    expect(contrast(t[`band-${band}`] ?? "", t[`on-band-${band}`] ?? "")).toBeGreaterThanOrEqual(4.5);
  });

  it.each(["text", "text-muted", "accent"])("%s reaches 4.5:1 on the page and on cards", (name) => {
    expect(contrast(t[name] ?? "", t["bg"] ?? "")).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t[name] ?? "", t["surface"] ?? "")).toBeGreaterThanOrEqual(4.5);
  });
});
