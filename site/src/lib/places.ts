import placesFile from "../data/places.json";

/** One city, town or named community with people in a district, from places.json. */
export interface Place {
  name: string;
  /** The Census type in plain words: "city", "town", "village", "community" and so on. */
  kind: string;
  /** Its 2020 residents in this district. */
  pop: number;
  /** All of its 2020 residents. */
  place_pop: number;
}

/** A district's largest places, from places.json. */
export interface DistrictPlaces {
  id: string;
  places: Place[];
  /** How many smaller places with people in the district aren't listed. */
  more: number;
  /** Share (0 to 1) of the district's 2020 residents who live in any place. */
  in_places: number;
}

const byId = new Map((placesFile.districts as DistrictPlaces[]).map((d) => [d.id, d]));
const count = new Intl.NumberFormat("en-US");

/**
 * Find a district's places.
 * @param id - A district ID such as `LA-02`.
 * @returns Its largest places (largest first), how many more there are, and the share in any place.
 * @throws Error if there is no such district.
 */
export function getPlaces(id: string): DistrictPlaces {
  const record = byId.get(id);
  if (!record) {
    throw new Error(`Unknown district: ${id}`);
  }
  return record;
}

/**
 * Say how many of a place's residents live in the district.
 * @param p - A place.
 * @returns "all 143,507 residents" for a place wholly in the district, else "155,032 of its 227,470 residents".
 */
export function placeCountText(p: Place): string {
  if (p.pop >= p.place_pop) {
    return `all ${count.format(p.place_pop)} residents`;
  }
  return `${count.format(p.pop)} of its ${count.format(p.place_pop)} residents`;
}

/**
 * Say how much of a district lives outside any place.
 * @param inPlaces - Share (0 to 1) of the district's residents in any place.
 * @returns A sentence with a whole percent (1% at least, 99% at most), or null if under half a percent live outside.
 */
export function outsidePlacesText(inPlaces: number): string | null {
  const outside = 1 - inPlaces;
  if (outside < 0.005) {
    return null;
  }
  const pct = Math.min(99, Math.max(1, Math.round(outside * 100)));
  return `${pct}% of this district's people live outside any city, town or named community.`;
}
