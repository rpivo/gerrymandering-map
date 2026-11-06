import senatorsFile from "../data/senators.json";

/** A U.S. senator, with their party in words. */
export interface Senator {
  name: string;
  party: "Democrat" | "Republican" | "Independent";
}

const byState = senatorsFile.states as Record<string, Senator[]>;

/** The date the Senate's list was downloaded, as YYYY-MM-DD. */
export const senatorsAsOf: string = senatorsFile.as_of;

/**
 * Return a state's senators.
 * @param usps A state's two-letter code, such as "ME".
 * @returns Its two senators, by last name, or an empty list for an unknown code.
 */
export function getSenators(usps: string): Senator[] {
  return byState[usps] ?? [];
}

/**
 * Write a date in words.
 * @param iso A date as YYYY-MM-DD.
 * @returns The date as "November 6, 2026".
 */
export function asOfDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  return date.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
}
