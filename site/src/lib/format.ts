/**
 * Return a number with its English ordinal suffix.
 * @param n - A positive whole number.
 * @returns For example "1st" or "22nd".
 */
export function ordinal(n: number): string {
  const lastTwo = n % 100;
  if (lastTwo >= 11 && lastTwo <= 13) {
    return `${n}th`;
  }
  const suffix = { 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th";
  return `${n}${suffix}`;
}

/**
 * Return a district's display name.
 * @param stateName - The state's full name.
 * @param number - The district number, or null for at-large.
 * @returns For example "Texas District 35".
 */
export function districtTitle(stateName: string, number: number | null): string {
  return number === null ? `${stateName} At-Large District` : `${stateName} District ${number}`;
}

/**
 * Return the share of ranked districts this one is less compact than.
 * Based on the national rank, so "less compact than X% of districts" is exactly true.
 * @param rank - National rank, 1 being the most irregular.
 * @param total - How many districts are ranked.
 * @returns A whole percent from 0 to 100.
 * @throws Error if rank is outside 1..total.
 */
export function lessCompactThan(rank: number, total: number): number {
  if (rank < 1 || rank > total) {
    throw new Error(`Rank ${rank} is outside 1..${total}.`);
  }
  return Math.round((100 * (total - rank)) / (total - 1));
}

/** A named range of irregularity scores, for color and labels. */
export interface ScoreBand {
  key: string;
  label: string;
}

const BANDS: { min: number; band: ScoreBand }[] = [
  { min: 80, band: { key: "very-irregular", label: "Very irregular" } },
  { min: 60, band: { key: "irregular", label: "Irregular" } },
  { min: 40, band: { key: "middle", label: "Middle of the pack" } },
  { min: 20, band: { key: "compact", label: "Compact" } },
  { min: 0, band: { key: "very-compact", label: "Very compact" } },
];

/**
 * Return the band an irregularity score falls in.
 * @param score - An irregularity score from 0 to 100.
 * @returns The band's key (for CSS) and label.
 * @throws Error if the score is outside 0..100.
 */
export function scoreBand(score: number): ScoreBand {
  const match = BANDS.find(({ min }) => score >= min);
  if (!match || score > 100) {
    throw new Error(`Score ${score} is outside 0..100.`);
  }
  return match.band;
}

/**
 * Describe a measure's percentile in words, avoiding "0%" for the very lowest.
 * @param pct - Percentile from 0 to 100: the share of districts at or below this value.
 * @returns A phrase such as "at least as compact as 63% of districts on this measure".
 */
export function measurePercentileText(pct: number): string {
  if (pct >= 100) {
    return "the most compact district on this measure";
  }
  if (pct < 1) {
    return "among the least compact 1% of districts on this measure";
  }
  return `at least as compact as ${Math.round(pct)}% of districts on this measure`;
}

/**
 * Describe a data source for the methodology page's credits.
 * Drops the trailing " Page: <url>" (the publisher's name already links there) and ends each part with one period.
 * @param description - The source's description from sources.json.
 * @param license - Its license, such as "Public domain (U.S. Government work)".
 * @param downloaded - The download date, YYYY-MM-DD.
 * @returns A sentence such as "TIGER/Line 2020 blocks. Public domain (U.S. Government work). Downloaded 2026-11-04."
 */
export function sourceNote(description: string, license: string, downloaded: string): string {
  const what = description.replace(/ Page: .*$/, "").replace(/\.$/, "");
  return `${what}. ${license}. Downloaded ${downloaded}.`;
}
