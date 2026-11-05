import { describe, expect, it } from "vitest";

import { darkTokens, lightTokens } from "./tokens";

/** A #rrggbb color's red, green and blue channels, in linear light (0 to 1). */
function linearRgb(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
}

/** WCAG relative luminance of a #rrggbb color. */
function luminance(hex: string): number {
  const [r, g, b] = linearRgb(hex);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

// How red-green color blind readers see a color (Machado, Oliveira and Fernandes 2009, full
// severity), as a matrix on linear RGB.
const COLOR_BLINDNESS: Record<string, number[][]> = {
  normal: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  deuteranopia: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
  protanopia: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
};

/** CIE lightness (L*, 0 black to 100 white) of a color as a reader with the given vision sees it. */
function lightness(hex: string, vision: string): number {
  const rgb = linearRgb(hex);
  const [r, g, b] = (COLOR_BLINDNESS[vision] ?? []).map((row) =>
    Math.min(1, Math.max(0, row.reduce((sum, m, i) => sum + m * (rgb[i] ?? 0), 0))),
  ) as [number, number, number];
  const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return y > 0.008856 ? 116 * Math.cbrt(y) - 16 : 903.3 * y;
}

/** WCAG contrast ratio between two #rrggbb colors, from 1 to 21. */
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const light = lightTokens();
const dark = darkTokens();
const bands = ["very-compact", "compact", "middle", "irregular", "very-irregular"];
// The smallest lightness difference (L*) between neighboring bands that still reads as a step.
const MIN_LIGHTNESS_STEP = 7;

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

  // Hue alone can't order the bands for red-green color blind readers, so lightness must: each
  // band stands further from the page background than the one before it.
  it.each(Object.keys(COLOR_BLINDNESS))("bands step in lightness, away from the page, with %s vision", (vision) => {
    const steps = bands.map((b) => lightness(t[`band-${b}`] ?? "", vision));
    const away = lightness(t["bg"] ?? "", "normal") > 50 ? -1 : 1;
    const gaps = steps.slice(1).map((l, i) => away * (l - (steps[i] ?? 0)));
    expect(gaps).toHaveLength(4);
    expect(Math.min(...gaps)).toBeGreaterThanOrEqual(MIN_LIGHTNESS_STEP);
  });

  it("runs from green (very compact) through yellow to red (very irregular)", () => {
    const [r1, g1, b1] = linearRgb(t["band-very-compact"] ?? "");
    const [r3, g3, b3] = linearRgb(t["band-middle"] ?? "");
    const [r5, g5, b5] = linearRgb(t["band-very-irregular"] ?? "");
    expect(g1).toBeGreaterThan(Math.max(r1, b1));
    expect(Math.min(r3, g3)).toBeGreaterThan(b3);
    expect(r5).toBeGreaterThan(Math.max(g5, b5));
  });

  it.each(["text", "text-muted", "accent"])("%s reaches 4.5:1 on the page and on cards", (name) => {
    expect(contrast(t[name] ?? "", t["bg"] ?? "")).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t[name] ?? "", t["surface"] ?? "")).toBeGreaterThanOrEqual(4.5);
  });
});
