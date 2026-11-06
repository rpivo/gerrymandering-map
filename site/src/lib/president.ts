import presidentFile from "../data/president-2024.json";

/** How a district's 2024 result was found (see the pipeline's gerry.votes). */
export type VoteMethod = "precinct join" | "official report" | "statewide";

/** One district's 2024 presidential vote: each candidate's 0 to 1 share of the two-party vote. */
export interface PresidentVote {
  harris: number;
  trump: number;
  method: VoteMethod;
}

const byId = presidentFile.districts as Record<string, PresidentVote>;

/**
 * Return a district's 2024 presidential vote.
 * @param id A district ID, such as "NE-02".
 * @returns Its vote, or undefined where none is measured on its lines.
 */
export function getPresident(id: string): PresidentVote | undefined {
  return byId[id];
}

/**
 * Format a share as a percent.
 * @param share A 0 to 1 share.
 * @returns The percent with one decimal place, such as "52.3%".
 */
export function percent(share: number): string {
  return `${(share * 100).toFixed(1)}%`;
}

/**
 * Say where a district's result comes from.
 * @param method How the result was found.
 * @param stateName The district's state, such as "Texas".
 * @returns One or two sentences for the district page.
 */
export function voteSource(method: VoteMethod, stateName: string): string {
  switch (method) {
    case "precinct join":
      return (
        `${stateName} used the same lines in 2024, so this is added up from precinct results. ` +
        "A precinct split between districts is divided by its House votes, so the figures are close estimates."
      );
    case "official report":
      return `${stateName} published 2024 results on its 2026 lines, and these are its figures.`;
    case "statewide":
      return "One district covers the state, so this is the whole state's vote.";
  }
}
