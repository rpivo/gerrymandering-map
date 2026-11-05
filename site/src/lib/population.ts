import populationFile from "../data/population.json";

/** A minority group in population.json. */
export type Group = "hispanic" | "black" | "aian" | "asian" | "nhpi";

/** One district's 2020 voting-age population, as 0 to 1 shares, from population.json. */
export interface Population {
  id: string;
  vap: number;
  hispanic: number;
  white: number;
  black: number;
  aian: number;
  asian: number;
  nhpi: number;
  minority: number;
  majority: Group | "coalition" | null;
}

export const population = populationFile.districts as Population[];

const byId = new Map(population.map((p) => [p.id, p]));

const GROUP_NAMES: Record<Group, string> = {
  hispanic: "Hispanic or Latino",
  black: "Black",
  aian: "American Indian or Alaska Native",
  asian: "Asian",
  nhpi: "Native Hawaiian or Pacific Islander",
};
// A coalition note names minority groups of at least this share, up to three of them.
const NAMED_GROUP_MIN = 0.1;

/**
 * Find a district's population record.
 * @param id - A district ID such as `AL-07`.
 * @returns Its 2020 voting-age shares.
 * @throws Error if there is no such district.
 */
export function getPopulation(id: string): Population {
  const record = byId.get(id);
  if (!record) {
    throw new Error(`Unknown district: ${id}`);
  }
  return record;
}

const pct = (share: number): string => `${(share * 100).toFixed(1)}%`;
const named = (group: Group, p: Population): string => `${GROUP_NAMES[group]} (${pct(p[group])})`;

function listed(items: string[]): string {
  return items.length < 3 ? items.join(" and ") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
}

/**
 * Describe a majority-minority district's voting-age population.
 * @param p - A district's population record.
 * @returns One or two sentences naming the majority group, or the minority total and the
 *   largest groups for a coalition; null if minority residents are not a majority.
 */
export function populationText(p: Population): string | null {
  if (p.majority === null) {
    return null;
  }
  const lead = "Most of this district's voting-age residents";
  if (p.majority !== "coalition") {
    return `${lead} are ${named(p.majority, p)}.`;
  }
  const groups = (Object.keys(GROUP_NAMES) as Group[]).sort((a, b) => p[b] - p[a]);
  const large = groups.filter((g) => p[g] >= NAMED_GROUP_MIN).slice(0, 3);
  const shown = large.length > 0 ? large : groups.slice(0, 1);
  const largest = shown.length === 1 ? "The largest is" : "The largest are";
  return `${lead} (${pct(p.minority)}) belong to minority groups. ${largest} ${listed(shown.map((g) => named(g, p)))}.`;
}
