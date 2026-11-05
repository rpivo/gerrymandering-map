import usMapFile from "../data/us-map.json";

/** The 50 states as one map, from us-map.json. Coordinates are in the map's viewBox units. */
export interface UsMap {
  viewBox: string;
  paths: Record<string, string>;
  /** A point well inside each state, for its label. */
  labels: Record<string, number[]>;
}

/**
 * States too small to label or click easily on the map. They get labeled boxes beside it,
 * north to south, as printed US maps do.
 */
export const CALLOUT_STATES = ["VT", "NH", "MA", "RI", "CT", "NJ", "DE", "MD"];

// Boxes are this far apart at least (viewBox units), and this far right of the map.
const CALLOUT_SPACING = 32;
const CALLOUT_MARGIN = 16;

/** One small state's box beside the map. */
export interface Callout {
  state: string;
  /** The box's left edge and vertical center. */
  x: number;
  y: number;
  /** The state's label point, where its leader line starts. */
  from: number[];
}

/**
 * Return the US map.
 * @returns The 50 states drawn together, with a label point for each.
 */
export function usMap(): UsMap {
  return usMapFile as UsMap;
}

/**
 * Place the small states' boxes in a column right of the map, each level with its state
 * unless that would crowd the box above it.
 * @param map - The US map.
 * @returns One box per state in CALLOUT_STATES, top to bottom.
 */
export function callouts(map: UsMap): Callout[] {
  const width = Number(map.viewBox.split(" ")[2] ?? 0);
  const placed: Callout[] = [];
  const north = [...CALLOUT_STATES].sort((a, b) => (map.labels[a]?.[1] ?? 0) - (map.labels[b]?.[1] ?? 0));
  for (const state of north) {
    const from = map.labels[state] ?? [0, 0];
    const above = placed.at(-1);
    const level = from[1] ?? 0;
    const y = above ? Math.max(level, above.y + CALLOUT_SPACING) : level;
    placed.push({ state, x: width + CALLOUT_MARGIN, y, from });
  }
  return placed;
}
