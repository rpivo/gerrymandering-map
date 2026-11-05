import citiesFile from "../data/cities.json";
import { getDistrict, stateMap, type StateCloseup } from "./data";
import { pathBounds } from "./tooltip";

type Box = [number, number, number, number];

/** A close-up ready to draw: the pipeline's box, with a name and how much it enlarges. */
export interface Closeup extends StateCloseup {
  /** "Los Angeles area": named after the biggest city whose point is in the box. */
  name: string;
  /** The box in the state map's viewBox units, even for a close-up of a close-up. */
  mapBox: Box;
  /** How many times larger than the state map it draws, for the same drawn size. */
  zoom: number;
  /** Drawn across the whole width, since it enlarges what it's beside least and needs the room most. */
  wide: boolean;
}

/** Close-ups that enlarge what they're drawn beside (the map, or their parent) less than this are drawn wide. */
export const WIDE_BELOW_ZOOM = 6;

const cityData = citiesFile as { states: Record<string, { cities: { name: string; x: number; y: number }[] }> };

function inside(box: Box, x: number, y: number): boolean {
  const [x0, y0, x1, y1] = box;
  return x >= x0 && x <= x1 && y >= y0 && y <= y1;
}

/**
 * Return how many units a box's close-up draws per unit of what it enlarges.
 *
 * @param box - The box, in the units of what it enlarges.
 * @returns The scale: 1000 over the box's longer side.
 */
function step(box: Box): number {
  return 1000 / Math.max(box[2] - box[0], box[3] - box[1]);
}

/**
 * Return a state map's close-ups, largest first, each followed by any close-ups of it.
 *
 * @param state - Two-letter state code.
 * @returns The close-ups, or none when every district is big enough to see on the map.
 */
export function closeups(state: string): Closeup[] {
  const cities = cityData.states[state]?.cities ?? [];
  const found: Closeup[] = [];
  const cityOf: string[] = [];
  for (const c of stateMap(state).closeups) {
    const parent = c.parent === undefined ? undefined : found[c.parent];
    // A nested box is in its parent's drawing: map it back to the state map's units.
    let mapBox = c.box;
    if (parent) {
      const [px, py] = parent.mapBox;
      const s = step(parent.mapBox);
      mapBox = [px + c.box[0] / s, py + c.box[1] / s, px + c.box[2] / s, py + c.box[3] / s];
    }
    // Cities are listed biggest first.
    const city = cities.find((p) => inside(mapBox, p.x, p.y))?.name;
    if (!city) throw new Error(`No city in a ${state} close-up to name it by`);
    const name = parent && c.parent !== undefined && cityOf[c.parent] === city ? `${parent.name}, closer in` : `${city} area`;
    found.push({ ...c, name, mapBox, zoom: step(mapBox), wide: step(c.box) < WIDE_BELOW_ZOOM });
    cityOf.push(city);
  }
  return found;
}

/**
 * Return the closest close-up a district lies wholly inside, for its district page.
 *
 * @param id - District ID, such as "CA-34".
 * @returns The close-up that enlarges it most, or undefined when it isn't wholly inside one.
 */
export function closeupFor(id: string): Closeup | undefined {
  const { state } = getDistrict(id);
  const path = stateMap(state).paths[id];
  if (!path) return undefined;
  const { minX, minY, maxX, maxY } = pathBounds(path);
  return closeups(state)
    .filter((c) => inside(c.mapBox, minX, minY) && inside(c.mapBox, maxX, maxY))
    .sort((a, b) => b.zoom - a.zoom)[0];
}
