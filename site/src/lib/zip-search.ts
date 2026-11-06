import zipsFile from "../data/zips.json";

/** A district a ZIP code has residents in, with the percent of the ZIP code's residents there. */
export type ZipDistrict = [id: string, percent: number];

/** ZIP codes sharing their first three digits, each with its districts, largest share first. */
export type ZipGroup = Record<string, ZipDistrict[]>;

/**
 * Read a search query as a ZIP code.
 * @param query What the visitor typed.
 * @returns The five-digit ZIP code, or undefined when the query isn't one.
 */
export function zipQuery(query: string): string | undefined {
  const trimmed = query.trim();
  return /^\d{5}$/.test(trimmed) ? trimmed : undefined;
}

/**
 * Name the index file a ZIP code is in.
 * @param zip A five-digit ZIP code.
 * @returns Its first three digits, such as "782" for 78221.
 */
export function zipPrefix(zip: string): string {
  return zip.slice(0, 3);
}

/**
 * Turn the districts-to-ZIP-codes data around, grouped by each ZIP code's first three digits,
 * so the home page search can fetch one small file per lookup.
 * @returns Each group of ZIP codes, keyed by the three digits.
 */
export function zipIndex(): Map<string, ZipGroup> {
  const groups = new Map<string, ZipGroup>();
  const districts = zipsFile.districts as unknown as Record<string, [string, number][]>;
  for (const [id, zips] of Object.entries(districts)) {
    for (const [zip, share] of zips) {
      const group = groups.get(zipPrefix(zip)) ?? {};
      (group[zip] ??= []).push([id, Math.round(share * 100)]);
      groups.set(zipPrefix(zip), group);
    }
  }
  for (const group of groups.values()) {
    for (const list of Object.values(group)) list.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }
  return groups;
}

/**
 * Say which districts a searched ZIP code is in.
 * @param zip The ZIP code searched for.
 * @param districts Its districts from the index, or undefined when it isn't listed.
 * @returns One sentence for the results line.
 */
export function zipMessage(zip: string, districts: ZipDistrict[] | undefined): string {
  if (!districts?.length) {
    return (
      `No district found for ZIP code ${zip}. ZIP codes used only for PO boxes or a single ` +
      "organization aren't listed. Try your city or state instead."
    );
  }
  const [first, ...rest] = districts;
  if (!first) return "";
  if (rest.length === 0) return `ZIP code ${zip} is in ${first[0]}.`;
  const parts = [`${first[0]} (${first[1]}% of its residents)`, ...rest.map(([id, pct]) => `${id} (${pct}%)`)];
  const last = parts.pop();
  return `ZIP code ${zip} is split between ${parts.join(", ")} and ${last}.`;
}
