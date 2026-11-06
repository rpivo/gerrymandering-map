import zipsFile from "../data/zips.json";

/** A ZIP code with residents in a district, and the 0 to 1 share of its residents there. */
export interface DistrictZip {
  zip: string;
  share: number;
}

/** Districts with more ZIP codes than this show them in a box the reader opens. */
export const ZIPS_SHOWN_OPEN = 40;

// JSON arrays type as (string | number)[][], so the pairs are read as unknown first.
const byId = zipsFile.districts as unknown as Record<string, [string, number][]>;

/**
 * List a district's ZIP codes.
 * @param id A district ID, such as "TX-35".
 * @returns Its ZIP codes in numeric order, each with the share of its 2020 residents there.
 */
export function getZips(id: string): DistrictZip[] {
  return (byId[id] ?? []).map(([zip, share]) => ({ zip, share }));
}

/**
 * Write a ZIP code for the list.
 * @param z A ZIP code and its share.
 * @returns The ZIP code alone when all its residents live in the district, otherwise with
 *   the percent who do, such as "78222 (62%)".
 */
export function zipLabel(z: DistrictZip): string {
  return z.share >= 1 ? z.zip : `${z.zip} (${Math.round(z.share * 100)}%)`;
}

/**
 * Sum up a district's ZIP codes in a sentence or two.
 * @param zips The district's ZIP codes.
 * @returns How many there are and how many are split with other districts.
 */
export function zipSummary(zips: DistrictZip[]): string {
  const n = zips.length;
  const split = zips.filter((z) => z.share < 1).length;
  const first = n === 1 ? "1 ZIP code has" : `${n} ZIP codes have`;
  let second: string;
  if (split === 0) second = n === 1 ? "It lies wholly within it." : "All of them lie wholly within it.";
  else if (split === 1) second = "1 of them is split with another district.";
  else second = `${split} of them are split with other districts.`;
  return `${first} residents in this district. ${second}`;
}
