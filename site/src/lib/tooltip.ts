import { rankedCount, type District, type StateInfo } from "./data";
import { lessCompactThan, ordinal, stateEdgePercent } from "./format";
import type { Population } from "./population";

/** A shape's bounding box, in the map's own (viewBox) units. */
export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/**
 * Find the box around an SVG path made of absolute M, L and Z commands, as in shapes.json.
 * @param d - The path data.
 * @returns The smallest and largest x and y of its points.
 * @throws Error if the path has no points.
 */
export function pathBounds(d: string): Bounds {
  const numbers = (d.match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number);
  if (numbers.length < 2) {
    throw new Error("The path has no points.");
  }
  const xs = numbers.filter((_, i) => i % 2 === 0);
  const ys = numbers.filter((_, i) => i % 2 === 1);
  return { minX: Math.min(...xs), minY: Math.min(...ys), maxX: Math.max(...xs), maxY: Math.max(...ys) };
}

/** Where a district's tooltip goes, in percent of the map's width (x) and height (y). */
export interface Placement {
  x: number;
  y: number;
  /** Above or below the district at y, or centered over it when neither side has room. */
  side: "above" | "below" | "over";
  /** Which edge of the tooltip lines up with x, so tooltips near the sides stay on the map. */
  align: "start" | "center" | "end";
}

// Below this percent the state's edge barely affects the score, so the short tooltip leaves it out.
// The district page still gives the exact share.
const EDGE_NOTE_MIN = 10;

// A tooltip needs about a quarter of the map's height; with less room above and below, it sits over the district.
const MIN_ROOM = 0.25;

/**
 * Place a district's tooltip next to it, on the side with more room.
 * @param b - The district's bounds, in viewBox units.
 * @param viewBox - The map's viewBox, "minX minY width height".
 * @returns The anchor point in percent of the map, and how the tooltip sits against it.
 */
export function tipPlacement(b: Bounds, viewBox: string): Placement {
  const [x0, y0, w, h] = viewBox.split(/\s+/).map(Number) as [number, number, number, number];
  const x = ((b.minX + b.maxX) / 2 - x0) / w * 100;
  const align = x < 30 ? "start" : x > 70 ? "end" : "center";
  const above = b.minY - y0;
  const below = y0 + h - b.maxY;
  if (Math.max(above, below) < MIN_ROOM * h) {
    return { x, y: ((b.minY + b.maxY) / 2 - y0) / h * 100, side: "over", align };
  }
  return above >= below
    ? { x, y: above / h * 100, side: "above", align }
    : { x, y: (b.maxY - y0) / h * 100, side: "below", align };
}

/** What a district's tooltip says. */
export interface TooltipText {
  heading: string;
  lines: string[];
  notes: string[];
}

/**
 * Write a district's tooltip: its score and ranks, then short context notes.
 * @param d - The district.
 * @param state - Its state.
 * @param majority - Its majority-minority group from population.json, or null if it has none.
 * @returns The heading (the district ID), the score lines and any notes.
 */
export function tooltipLines(d: District, state: StateInfo, majority: Population["majority"]): TooltipText {
  const notes: string[] = [];
  let lines: string[];
  if (d.at_large || d.irregularity === null || d.rank_national === null || d.rank_state === null) {
    lines = ["One district covers the whole state, so it isn't scored"];
  } else {
    lines = [
      `Irregularity score ${d.irregularity}`,
      `Less compact than ${lessCompactThan(d.rank_national, rankedCount)}% of districts`,
      `${ordinal(d.rank_state)} least compact of ${state.seats} in ${state.name}`,
    ];
    const edge = stateEdgePercent(d.state_edge_share);
    if (edge >= EDGE_NOTE_MIN) {
      notes.push(`${edge}% of its border is the state's edge`);
    }
  }
  if (majority !== null) {
    notes.push("Majority-minority (2020 voting-age population)");
  }
  if (d.redrawn_2026) {
    notes.push("New lines for 2026");
  }
  return { heading: d.id, lines, notes };
}
