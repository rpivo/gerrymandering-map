import { describe, expect, it } from "vitest";

import { assertFontsLoad, renderPng } from "./og-render";

/** Read a PNG's width and height from its IHDR chunk. */
function pngSize(png: Uint8Array): { width: number; height: number } {
  const view = new DataView(png.buffer, png.byteOffset, png.byteLength);
  return { width: view.getUint32(16), height: view.getUint32(20) };
}

const blank = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630"><rect width="1200" height="630" fill="#fff"/>`;

describe("renderPng", () => {
  it("returns a 1200 by 630 PNG", () => {
    const png = renderPng(`${blank}</svg>`);
    expect([...png.slice(0, 8)]).toEqual([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    expect(pngSize(png)).toEqual({ width: 1200, height: 630 });
  });

  it("finds the bundled font, so the build's font check passes", () => {
    expect(() => assertFontsLoad()).not.toThrow();
  });

  it("draws text with the bundled font, regular and bold", () => {
    // System fonts are off, so without the bundled font the text would draw nothing.
    const empty = renderPng(`${blank}</svg>`);
    const [regular, bold] = ["400", "700"].map((weight) =>
      renderPng(`${blank}<text x="40" y="200" font-size="96" font-weight="${weight}">TX-35</text></svg>`),
    );
    expect(regular).not.toEqual(empty);
    // resvg doesn't fake bold, so a missing bold file would draw it the same as regular.
    expect(bold).not.toEqual(regular);
  });
});
