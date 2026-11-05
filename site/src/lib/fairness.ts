import fairnessFile from "../data/fairness.json";

/** Why a state has fairness scores, or why it doesn't. */
export type FairnessStatus = "scored" | "at_large" | "too_few_districts" | "awaiting_2026_results" | "no_vote_data";

/** One state's partisan fairness, as written by the pipeline to fairness.json. Positive favors Republicans. */
export interface Fairness {
  state: string;
  status: FairnessStatus;
  districts: number | null;
  dem_vote_share: number | null;
  dem_seats: number | null;
  one_party_won_every_district: boolean | null;
  efficiency_gap: number | null;
  mean_median: number | null;
  declination: number | null;
  method: "precinct join" | "official report" | null;
}

export const fairness = fairnessFile.states as Fairness[];

const byState = new Map(fairness.map((f) => [f.state, f]));

/** The smallest number of districts the pipeline scores (MIN_DISTRICTS in gerry.fairness). */
export const MIN_DISTRICTS = 4;

/**
 * Find a state's fairness record.
 * @param usps - A two-letter state code.
 * @returns Its record, scored or with a status saying why not.
 * @throws Error if there is no such state.
 */
export function getFairness(usps: string): Fairness {
  const record = byState.get(usps);
  if (!record) {
    throw new Error(`Unknown state: ${usps}`);
  }
  return record;
}

/**
 * Say which party a score favors, judged on the number as shown so the words never disagree with it.
 * @param value - A score where positive favors Republicans.
 * @param places - Decimal places it is shown with (on its 0 to 1 scale).
 * @returns "Favors Republicans", "Favors Democrats" or "Neutral".
 */
export function leanText(value: number, places: number): string {
  const shown = Math.round(Math.abs(value) * 10 ** places);
  if (shown === 0) {
    return "Neutral";
  }
  return value > 0 ? "Favors Republicans" : "Favors Democrats";
}

function scoredFields(f: Fairness): { share: number; seats: number; districts: number } {
  if (f.status !== "scored" || f.dem_vote_share === null || f.dem_seats === null || f.districts === null) {
    throw new Error(`${f.state} has no fairness scores.`);
  }
  return { share: f.dem_vote_share, seats: f.dem_seats, districts: f.districts };
}

/**
 * Summarize the 2024 presidential vote in a scored state.
 * @param f - A scored state's record.
 * @returns A sentence with the Democratic two-party share and the districts each side carried.
 * @throws Error if the state has no scores.
 */
export function voteSummary(f: Fairness): string {
  const { share, seats, districts } = scoredFields(f);
  const won = `Kamala Harris (Democrat) won ${(share * 100).toFixed(1)}% of the two-party vote`;
  if (seats === 0) {
    return `${won}. Donald Trump (Republican) carried all ${districts} districts.`;
  }
  const carried = seats === districts ? `all ${districts}` : `${seats} of ${districts}`;
  return `${won} and carried ${carried} districts.`;
}

/**
 * Explain why a state has no fairness scores.
 * @param f - An unscored state's record.
 * @param seats - The state's number of districts.
 * @returns One or two sentences.
 * @throws Error if the state is scored.
 */
export function unscoredReason(f: Fairness, seats: number): string {
  switch (f.status) {
    case "at_large":
      return "One district covers the whole state, so there are no lines to score.";
    case "too_few_districts":
      return `With only ${seats} districts, one seat changing hands swings these measures too far to mean much, so the site scores states with ${MIN_DISTRICTS} or more.`;
    case "awaiting_2026_results":
      return "This state drew new districts for 2026, and no official 2024 results exist for the new lines. Scores will use the 2026 House results once they are final.";
    case "no_vote_data":
      return "The site doesn't have vote data for this state yet.";
    case "scored":
      throw new Error(`${f.state} is scored.`);
  }
}
