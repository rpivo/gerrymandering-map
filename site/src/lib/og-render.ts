import { Resvg } from "@resvg/resvg-js";

// Node's global, typed here so the site doesn't need @types/node for one call.
declare const process: { cwd(): string };

// Resolved from the working directory, which is site/ for `astro build`, Vitest and Cloudflare's build.
// A `new URL(..., import.meta.url)` path breaks in the build, where Vite moves the module.
const FONT_DIR = `${process.cwd()}/src/assets/fonts`;
const FONT_FILES = ["Inter-Regular.ttf", "Inter-Bold.ttf"].map((name) => `${FONT_DIR}/${name}`);

/**
 * Render with the bundled fonts only. resvg skips a font file it can't read without saying so.
 * @param svg - An SVG document.
 * @returns PNG bytes.
 */
function render(svg: string): Uint8Array {
  const resvg = new Resvg(svg, {
    font: { loadSystemFonts: false, fontFiles: FONT_FILES, defaultFontFamily: "Inter" },
    fitTo: { mode: "original" },
  });
  return resvg.render().asPng();
}

const probe = (text: string) => `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><text x="4" y="30" font-size="28">${text}</text></svg>`;

/**
 * Fail loudly if the bundled font didn't load, since every card would otherwise build without text.
 * @throws Error naming the font folder when text draws nothing.
 */
export function assertFontsLoad(): void {
  const blank = render(probe(""));
  const drawn = render(probe("Aa"));
  if (blank.length === drawn.length && blank.every((byte, i) => byte === drawn[i])) {
    throw new Error(`Preview cards can't draw text: no font loaded from ${FONT_DIR}.`);
  }
}

/**
 * Render an SVG document to PNG with the bundled Inter font.
 * System fonts are off, so the image looks the same on every machine that builds the site.
 * @param svg - An SVG document with explicit width and height.
 * @returns The PNG file's bytes, at the SVG's own size in pixels.
 */
export function renderPng(svg: string): Uint8Array {
  return render(svg);
}
