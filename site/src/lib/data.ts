import districtsFile from "../data/districts.json";
import shapesFile from "../data/shapes.json";
import sourcesFile from "../data/sources.json";
import statesFile from "../data/states.json";

/** One district's scores, as written by the pipeline to districts.json. */
export interface District {
  id: string;
  state: string;
  number: number | null;
  at_large: boolean;
  redrawn_2026: boolean;
  map_source: string;
  polsby_popper: number;
  reock: number;
  convex_hull: number;
  schwartzberg: number;
  /** Share (0 to 1) of the district's border on the state's edge: coast, national border or state line. */
  state_edge_share: number;
  polsby_popper_pct: number | null;
  reock_pct: number | null;
  convex_hull_pct: number | null;
  irregularity: number | null;
  rank_national: number | null;
  rank_state: number | null;
}

/** One state's details, as written to states.json from the state map audit. */
export interface StateInfo {
  state: string;
  name: string;
  seats: number;
  at_large: boolean;
  changed_since_2024: boolean;
  map_in_effect_2026: string;
  enacted: string | null;
  drawn_by: string;
  first_used: string;
  source_url: string;
  source_publisher: string;
  notes: string | null;
  confidence: string;
  checked: string;
}

/** A data source behind the map, as written to sources.json. */
export interface Source {
  id: string;
  publisher: string;
  description: string;
  url: string;
  license: string;
  downloaded: string;
  role: "boundaries" | "calibration" | "votes";
}

/** An SVG outline: a viewBox and a path. */
export interface Outline {
  viewBox: string;
  d: string;
}

/** A state's districts drawn together: one viewBox, a path per district. */
export interface StateMap {
  viewBox: string;
  paths: Record<string, string>;
}

interface ShapesFile {
  districts: Record<string, { card: Outline; page: Outline }>;
  states: Record<string, StateMap>;
}

export const districts = districtsFile.districts as District[];
export const states = (statesFile.states as StateInfo[])
  .slice()
  .sort((a, b) => a.name.localeCompare(b.name));
export const sources = sourcesFile.sources as Source[];
const shapes = shapesFile as unknown as ShapesFile;

/** How many districts are ranked: all except the at-large ones. */
export const rankedCount = districts.filter((d) => !d.at_large).length;

const byId = new Map(districts.map((d) => [d.id, d]));
const byState = new Map(states.map((s) => [s.state, s]));

/**
 * Find a district.
 * @param id - A district ID such as `TX-35`.
 * @returns The district.
 * @throws Error if there is no such district.
 */
export function getDistrict(id: string): District {
  const district = byId.get(id);
  if (!district) {
    throw new Error(`Unknown district: ${id}`);
  }
  return district;
}

/**
 * Find a state.
 * @param usps - A two-letter state code.
 * @returns The state.
 * @throws Error if there is no such state.
 */
export function getState(usps: string): StateInfo {
  const state = byState.get(usps);
  if (!state) {
    throw new Error(`Unknown state: ${usps}`);
  }
  return state;
}

/**
 * List a state's districts.
 * @param usps - A two-letter state code.
 * @returns Its districts in number order.
 */
export function districtsInState(usps: string): District[] {
  return districts
    .filter((d) => d.state === usps)
    .sort((a, b) => (a.number ?? 0) - (b.number ?? 0));
}

/**
 * Get a district's outline.
 * @param id - A district ID.
 * @param kind - "card" (coarse, for grids) or "page" (detailed).
 * @returns The outline.
 */
export function outline(id: string, kind: "card" | "page"): Outline {
  const entry = shapes.districts[id];
  if (!entry) {
    throw new Error(`Unknown district: ${id}`);
  }
  return entry[kind];
}

/**
 * Get a state's map.
 * @param usps - A two-letter state code.
 * @returns The viewBox and a path per district.
 */
export function stateMap(usps: string): StateMap {
  const map = shapes.states[usps];
  if (!map) {
    throw new Error(`Unknown state: ${usps}`);
  }
  return map;
}

/**
 * Get the previous and next districts in the same state.
 * @param id - A district ID.
 * @returns Their IDs, or null at either end (both null for at-large districts).
 */
export function adjacent(id: string): { previous: string | null; next: string | null } {
  const siblings = districtsInState(getDistrict(id).state);
  const index = siblings.findIndex((d) => d.id === id);
  return {
    previous: siblings[index - 1]?.id ?? null,
    next: siblings[index + 1]?.id ?? null,
  };
}
