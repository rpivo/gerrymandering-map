/** A district ID split into its parts. `number` is null for at-large districts. */
export interface DistrictParts {
  state: string;
  number: number | null;
}

/**
 * Parse a district ID such as `TX-35` or `WY-AL`.
 * @param id - Two-letter state code, a hyphen, then a district number or `AL`.
 * @returns The state code and district number (null for at-large).
 * @throws Error if the ID is not in that format.
 */
export function parseDistrictId(id: string): DistrictParts {
  const match = DISTRICT_ID.exec(id);
  if (!match?.groups) {
    throw new Error(`Invalid district ID: ${JSON.stringify(id)}`);
  }
  const { state, district } = match.groups as { state: string; district: string };
  if (district === "AL") {
    return { state, number: null };
  }
  const number = Number(district);
  if (number < 1) {
    throw new Error(`Invalid district ID: ${JSON.stringify(id)}`);
  }
  return { state, number };
}

const DISTRICT_ID = /^(?<state>[A-Z]{2})-(?<district>AL|\d{1,2})$/;

/**
 * Build the site path for a district's page, such as `/tx/35` or `/wy/al`.
 * @param id - A district ID such as `TX-35`.
 * @returns The page path.
 */
export function districtPath(id: string): string {
  const { state, number } = parseDistrictId(id);
  return `/${state.toLowerCase()}/${number ?? "al"}`;
}
