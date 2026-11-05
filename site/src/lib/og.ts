import { districts, districtsInState, getDistrict, getState, outline, rankedCount, stateMap, type Outline } from "./data";
import { districtTitle, lessCompactThan, scoreBand } from "./format";
import { lightTokens } from "./tokens";

/** The site's public address, for the absolute URLs link previews need. Change it if the domain changes. */
export const SITE_URL = "https://gerrymandering-map.ryanpivovar.workers.dev";

const WIDTH = 1200;
const HEIGHT = 630;
// Inter's average glyph is a little over half its font size wide; used to size pills and wrap lines.
const CHAR_WIDTH = 0.5;
const TEXT_X = 600;
const t = lightTokens();

/**
 * Return the preview image path for a page.
 * @param page - A site path such as `/`, `/tx` or `/tx/35`.
 * @returns The image path, such as `/og/index.png` or `/og/tx/35.png`.
 */
export function ogImagePath(page: string): string {
  return page === "/" ? "/og/index.png" : `/og${page}.png`;
}

/**
 * Break text into lines between words.
 * @param text - The text.
 * @param max - The most characters a line should hold. A longer single word gets its own line.
 * @returns The lines, in order.
 */
export function wrapText(text: string, max: number): string[] {
  const lines: string[] = [];
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const last = lines.at(-1);
    if (last !== undefined && last.length + 1 + word.length <= max) {
      lines[lines.length - 1] = `${last} ${word}`;
    } else {
      lines.push(word);
    }
  }
  return lines;
}

/**
 * Escape text for use inside SVG markup.
 * @param text - Any text.
 * @returns The text with &, <, >, " and ' escaped.
 */
export function escapeXml(text: string): string {
  const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" };
  return text.replace(/[&<>"']/g, (c) => entities[c] ?? c);
}

interface TextLines {
  lines: string[];
  y: number;
  size: number;
  color: string;
  weight?: number;
  lineHeight?: number;
}

/**
 * Draw lines of text in the right-hand column.
 * @param block - The lines, the first baseline, font size and weight, color and line height.
 * @returns The markup, and the baseline of the last line.
 */
function textBlock(block: TextLines): { svg: string; y: number } {
  const { lines, y, size, color, weight = 400, lineHeight = 1.25 } = block;
  const step = Math.round(size * lineHeight);
  const svg = lines
    .map((line, i) => `<text x="${TEXT_X}" y="${y + i * step}" font-size="${size}" font-weight="${weight}" fill="${color}">${escapeXml(line)}</text>`)
    .join("");
  return { svg, y: y + (lines.length - 1) * step };
}

/**
 * Wrap card content in the 1200 by 630 frame, with the site name and the standing caveat.
 * @param art - Markup for the left-hand picture.
 * @param body - Markup for the right-hand text.
 * @returns A complete SVG document.
 */
function frame(art: string, body: string): string {
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}" font-family="Inter">`,
    `<rect width="${WIDTH}" height="${HEIGHT}" fill="${t["bg"]}"/>`,
    art,
    `<text x="${TEXT_X}" y="96" font-size="22" font-weight="700" letter-spacing="3" fill="${t["text-muted"]}">GERRYMANDERING MAP</text>`,
    body,
    `<text x="${TEXT_X}" y="574" font-size="24" fill="${t["text-muted"]}">Scores describe shape, not intent.</text>`,
    "</svg>",
  ].join("");
}

/**
 * Place an outline's own viewBox into a box on the card, centered and scaled to fit.
 * @param viewBox - The drawing's viewBox.
 * @param content - Markup in the drawing's coordinates.
 * @param box - Where on the card, in pixels: top-left corner and side length.
 * @returns A nested SVG element.
 */
function artBox(viewBox: string, content: string, box = { x: 60, y: 60, size: 510 }): string {
  return `<svg x="${box.x}" y="${box.y}" width="${box.size}" height="${box.size}" viewBox="${viewBox}" preserveAspectRatio="xMidYMid meet">${content}</svg>`;
}

/**
 * Draw one outline as a filled path.
 * @param shape - The outline.
 * @param fill - A #rrggbb color.
 * @returns A path element.
 */
function shapePath(shape: Outline, fill: string): string {
  return `<path d="${shape.d}" fill="${fill}" fill-rule="evenodd"/>`;
}

/**
 * Draw a rounded pill with one line of text, sized to the text.
 * @param text - The text.
 * @param y - The pill's top edge, in pixels.
 * @param fill - Background color.
 * @param color - Text color.
 * @param border - Optional border color.
 * @returns Markup for the pill and its text.
 */
function pill(text: string, y: number, fill: string, color: string, border?: string): string {
  const size = 34;
  const width = Math.round(text.length * size * CHAR_WIDTH + 56);
  const stroke = border ? ` stroke="${border}" stroke-width="2"` : "";
  return (
    `<rect x="${TEXT_X}" y="${y}" width="${width}" height="68" rx="34" fill="${fill}"${stroke}/>` +
    `<text x="${TEXT_X + 28}" y="${y + 46}" font-size="${size}" font-weight="700" fill="${color}">${escapeXml(text)}</text>`
  );
}

/**
 * Draw a district's preview card: its outline, ID, name, score and how it compares.
 * @param id - A district ID such as `TX-35`.
 * @returns A 1200 by 630 SVG document.
 */
export function districtCardSvg(id: string): string {
  const d = getDistrict(id);
  const state = getState(d.state);
  const heading = textBlock({ lines: [d.id], y: 196, size: 96, color: t["text"] ?? "", weight: 700 });
  const name = textBlock({ lines: wrapText(districtTitle(state.name, d.number), 26), y: heading.y + 62, size: 38, color: t["text-muted"] ?? "" });
  const pillY = name.y + 40;
  let score: string;
  let detail: string[];
  if (d.irregularity === null || d.rank_national === null) {
    score = pill("Not ranked (at-large)", pillY, t["surface"] ?? "", t["text-muted"] ?? "", t["border"]);
    detail = ["One district covers the whole state."];
  } else {
    const band = scoreBand(d.irregularity);
    score = pill(`Irregularity score ${d.irregularity}`, pillY, t[`band-${band.key}`] ?? "", t[`on-band-${band.key}`] ?? "");
    detail = [band.label, ...wrapText(`Less compact than ${lessCompactThan(d.rank_national, rankedCount)}% of other districts`, 24)];
  }
  const below = textBlock({ lines: detail, y: pillY + 112, size: 30, color: t["text"] ?? "" });
  return frame(artBox(outline(id, "page").viewBox, shapePath(outline(id, "page"), t["shape"] ?? "")), heading.svg + name.svg + score + below.svg);
}

/**
 * Draw a state's preview card: its districts shaded by score, with its name and district count.
 * @param usps - A two-letter state code.
 * @returns A 1200 by 630 SVG document.
 */
export function stateCardSvg(usps: string): string {
  const state = getState(usps);
  const map = stateMap(usps);
  const paths = districtsInState(usps)
    .map((d) => {
      const fill = d.irregularity === null ? t["shape"] : t[`band-${scoreBand(d.irregularity).key}`];
      return `<path d="${map.paths[d.id] ?? ""}" fill="${fill}" stroke="${t["bg"]}" stroke-width="3" fill-rule="evenodd"/>`;
    })
    .join("");
  const name = textBlock({ lines: wrapText(state.name, 13), y: 186, size: 68, color: t["text"] ?? "", weight: 700 });
  const count = state.at_large ? "One at-large district" : `${state.seats} congressional districts`;
  const facts = [count, ...(state.changed_since_2024 ? ["New lines for 2026"] : [])];
  const below = textBlock({ lines: facts, y: name.y + 74, size: 34, color: t["text-muted"] ?? "" });
  return frame(artBox(map.viewBox, paths), name.svg + below.svg);
}

/**
 * Draw the site-wide preview card: the twelve least compact outlines, with a title and subtitle.
 * @param title - The page title.
 * @param subtitle - One sentence about the page.
 * @returns A 1200 by 630 SVG document.
 */
export function siteCardSvg(title: string, subtitle: string): string {
  const top = districts
    .filter((d) => d.rank_national !== null)
    .sort((a, b) => (a.rank_national ?? 0) - (b.rank_national ?? 0))
    .slice(0, 12);
  const cell = 160;
  const art = top
    .map((d, i) => {
      const shape = outline(d.id, "card");
      const box = { x: 60 + (i % 3) * (cell + 15), y: 30 + Math.floor(i / 3) * (cell - 15), size: cell - 20 };
      return artBox(shape.viewBox, shapePath(shape, t["shape"] ?? ""), box);
    })
    .join("");
  const heading = textBlock({ lines: wrapText(title, 14), y: 186, size: 64, color: t["text"] ?? "", weight: 700 });
  const below = textBlock({ lines: wrapText(subtitle, 30), y: heading.y + 70, size: 32, color: t["text-muted"] ?? "" });
  return frame(art, heading.svg + below.svg);
}
