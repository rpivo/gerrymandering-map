import citiesFile from "../data/cities.json";

/** One of a state's largest places, as a point on its state map (viewBox units). */
export interface City {
  name: string;
  pop: number;
  x: number;
  y: number;
}

/** A city to mark: its dot, and which side of the dot its label goes ("start" is right). */
export interface CityMark {
  name: string;
  x: number;
  y: number;
  anchor: "start" | "end";
}

/** The marks for one range of map widths, with the label size in viewBox units. */
export interface CityTier {
  /** The map widths (CSS pixels) this tier is shown at: min up to but not including max. */
  min: number;
  max: number | null;
  /** The map width the label size is set for. Wider maps in the tier show bigger labels. */
  ref: number;
  fontSize: number;
  marks: CityMark[];
}

interface CitiesFile {
  states: Record<string, { viewBox: string; cities: City[] }>;
}

const data = citiesFile as CitiesFile;

/** Labels are this many CSS pixels tall on a map drawn at its tier's ref width. */
export const LABEL_PX = 11;
/** Marks per map at most, so the map stays readable. */
export const MAX_MARKS = 8;
// Map widths (CSS pixels) where the marks change. Labels scale with the map, so each tier's
// labels are 11 to about 14 pixels; a phone-width map is 290 to 400.
const TIER_MINS = [0, 400, 520, 680, 880];
// State maps are capped at 32rem tall (StateMapSvg), so a tall state is never drawn wide.
const MAX_MAP_HEIGHT = 512;

// Label geometry, as shares of the font size. Widths are an estimate for the site's sans
// serif, on the generous side so labels never touch.
const CHAR_WIDTH = 0.6;
const DOT_RADIUS = 0.25;
const LABEL_OFFSET = 0.55;
const PADDING = 0.15;

/**
 * Return the dot radius for a label size.
 *
 * @param fontSize - Label size in viewBox units.
 * @returns The radius, in viewBox units.
 */
export function dotRadius(fontSize: number): number {
  return DOT_RADIUS * fontSize;
}

/**
 * Return the gap from a dot's center to its label's near end.
 *
 * @param fontSize - Label size in viewBox units.
 * @returns The gap, in viewBox units.
 */
export function labelOffset(fontSize: number): number {
  return LABEL_OFFSET * fontSize;
}

/**
 * Return the box a mark's label takes up.
 *
 * @param mark - The city and the side its label goes on.
 * @param fontSize - Label size in viewBox units.
 * @returns [left, top, right, bottom] in viewBox units.
 */
export function labelBox(mark: CityMark, fontSize: number): number[] {
  const width = mark.name.length * CHAR_WIDTH * fontSize;
  const near = labelOffset(fontSize);
  const [left, right] =
    mark.anchor === "start" ? [mark.x + near, mark.x + near + width] : [mark.x - near - width, mark.x - near];
  return [left, mark.y - fontSize / 2, right, mark.y + fontSize / 2];
}

function overlaps(a: number[], b: number[], pad: number): boolean {
  const [ax0, ay0, ax1, ay1] = a as [number, number, number, number];
  const [bx0, by0, bx1, by1] = b as [number, number, number, number];
  return ax0 - pad < bx1 && bx0 < ax1 + pad && ay0 - pad < by1 && by0 < ay1 + pad;
}

function dotBox(city: { x: number; y: number }, fontSize: number): number[] {
  const r = dotRadius(fontSize);
  return [city.x - r, city.y - r, city.x + r, city.y + r];
}

/**
 * Pick which cities to mark on a map, largest first, so no label covers another label or a dot.
 *
 * @param cities - Candidates, largest first.
 * @param viewBox - The map's "0 0 w h"; labels must fit inside it.
 * @param fontSize - Label size in viewBox units.
 * @param max - Marks at most.
 * @returns The marks, largest city first. A city whose label fits on neither side is left out.
 */
export function placeCities(cities: City[], viewBox: string, fontSize: number, max: number): CityMark[] {
  const [, , width, height] = viewBox.split(/\s+/).map(Number) as [number, number, number, number];
  const pad = PADDING * fontSize;
  const marks: CityMark[] = [];
  const taken: number[][] = [];
  const inside = (b: number[]) => {
    const [left, top, right, bottom] = b as [number, number, number, number];
    return left >= 0 && top >= 0 && right <= width && bottom <= height;
  };
  for (const city of cities) {
    if (marks.length >= max) break;
    const dot = dotBox(city, fontSize);
    if (taken.some((t) => overlaps(dot, t, pad))) continue;
    for (const anchor of ["start", "end"] as const) {
      const mark = { name: city.name, x: city.x, y: city.y, anchor };
      const label = labelBox(mark, fontSize);
      if (!inside(label) || taken.some((t) => overlaps(label, t, pad))) continue;
      // Once a city is marked, later labels must also stay clear of its dot.
      if (marks.some((m) => overlaps(label, dotBox(m, fontSize), pad))) continue;
      marks.push(mark);
      taken.push(label, dot);
      break;
    }
  }
  return marks;
}

/**
 * Return a state map's city marks for each range of widths it can be drawn at.
 *
 * Label sizes are in viewBox units, so labels grow and shrink with the map and the marks that
 * fit at a tier's narrowest width fit across it. Wider tiers have room for more cities.
 *
 * @param state - Two-letter state code.
 * @returns Tiers narrowest first; the widest has max null.
 */
export function cityTiers(state: string): CityTier[] {
  const entry = data.states[state];
  if (!entry) throw new Error(`No cities for ${state}`);
  const [, , width, height] = entry.viewBox.split(/\s+/).map(Number) as [number, number, number, number];
  const widest = (MAX_MAP_HEIGHT * width) / height;
  const mins = TIER_MINS.filter((min) => min < widest);
  return mins.map((min, i) => {
    const ref = min === 0 ? 320 : min;
    const fontSize = (LABEL_PX * width) / ref;
    return {
      min,
      max: mins[i + 1] ?? null,
      ref,
      fontSize,
      marks: placeCities(entry.cities, entry.viewBox, fontSize, MAX_MARKS),
    };
  });
}
