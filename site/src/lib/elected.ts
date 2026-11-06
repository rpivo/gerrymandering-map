import electedFile from "../data/elected-2026.json";
import { asOfDate } from "./senators";

/** Who won a November 2026 race, as written by the pipeline's gerry.elected. */
export type Outcome =
  | { status: "elected"; name: string; party: string }
  | { status: "uncalled" }
  | { status: "runoff"; runoff_date: string }
  | { status: "pending" };

/** Which 2026 Senate race a seat was in. */
export type Seat = "regular" | "special";

const ELECTION = "November 3, 2026";
const SWORN_IN = "January 3, 2027";
const SUFFIXES = new Set(["jr", "sr", "ii", "iii", "iv"]);

/**
 * Describe a House race for a district page.
 * @param outcome The district's 2026 race.
 * @param stateName The district's state, such as "Michigan", for a pending race.
 * @returns The winner as "Name, Party" (undefined when there is none yet) and a sentence.
 */
export function houseLines(outcome: Outcome, stateName = ""): { winner: string | undefined; detail: string } {
  switch (outcome.status) {
    case "elected":
      return {
        winner: `${outcome.name}, ${outcome.party}`,
        detail: `Elected ${ELECTION}, takes office ${SWORN_IN}.`,
      };
    case "uncalled":
      return { winner: undefined, detail: `The ${ELECTION} race hasn't been called yet.` };
    case "runoff":
      return {
        winner: undefined,
        detail: `No candidate won a majority on ${ELECTION}, so the race goes to a runoff on ${asOfDate(outcome.runoff_date)}.`,
      };
    case "pending":
      return {
        winner: undefined,
        detail: `Statewide results from ${stateName} for the ${ELECTION} election aren't available yet.`,
      };
  }
}

/**
 * Say which 2026 race a senator's seat was in.
 * @param senateClass The seat's class: 1, 2 or 3.
 * @returns "regular" for class 2 (up in 2026), "special" for class 3 (special elections fill
 *   class 3 seats in 2026), otherwise undefined.
 */
export function seatOnBallot(senateClass: number): Seat | undefined {
  if (senateClass === 2) return "regular";
  if (senateClass === 3) return "special";
  return undefined;
}

/**
 * Tell whether a race's winner is the senator who held the seat, by last name.
 * @param last The senator's last name, from the Senate's list.
 * @param winner The winner's name as the state printed it.
 * @returns True when the winner's last name (ignoring Jr., III and so on) matches.
 */
export function isSamePerson(last: string, winner: string): boolean {
  const words = winner
    .toLowerCase()
    .replace(/[.,]/g, "")
    .split(/\s+/)
    .filter((w) => w && !SUFFIXES.has(w));
  return words.at(-1) === last.toLowerCase();
}

/**
 * Describe the 2026 race for a senator's seat.
 * @param last The senator's last name.
 * @param outcome The race for the seat.
 * @returns One sentence for the senator's line.
 */
export function senateBallotLine(last: string, outcome: Outcome): string {
  switch (outcome.status) {
    case "elected":
      return isSamePerson(last, outcome.name)
        ? `Re-elected ${ELECTION}.`
        : `Seat on the ${ELECTION} ballot: ${outcome.name}, ${outcome.party}, won and takes office ${SWORN_IN}.`;
    case "uncalled":
      return `Seat on the ${ELECTION} ballot: the race hasn't been called yet.`;
    case "runoff":
      return `Seat on the ${ELECTION} ballot: the race goes to a runoff on ${asOfDate(outcome.runoff_date)}.`;
    case "pending":
      return `Seat on the ${ELECTION} ballot: results aren't available yet.`;
  }
}

interface ElectedFile {
  called_as_of: string;
  house: Record<string, Outcome>;
  senate: Record<string, Partial<Record<Seat, Outcome>>>;
  sources: Record<string, { publisher: string; url: string; checked: string }>;
}

const elected = electedFile as ElectedFile;

/**
 * Return a district's November 2026 House race.
 * @param id A district ID, such as "ME-02".
 * @returns Its outcome, or undefined for an unknown ID.
 */
export function getHouseOutcome(id: string): Outcome | undefined {
  return elected.house[id];
}

/**
 * Return the November 2026 race for a Senate seat.
 * @param usps A state's two-letter code.
 * @param seat Which race: "regular" or "special".
 * @returns Its outcome, or undefined when that seat wasn't on the ballot.
 */
export function getSenateOutcome(usps: string, seat: Seat | undefined): Outcome | undefined {
  return seat ? elected.senate[usps]?.[seat] : undefined;
}

/**
 * Return where a state's results come from and when the uncalled list was checked.
 * @param usps A state's two-letter code.
 * @returns The state election office's results page and dates, or undefined.
 */
export function resultsSource(usps: string): { publisher: string; url: string; checked: string; calledAsOf: string } | undefined {
  const source = elected.sources[usps];
  return source && { ...source, calledAsOf: elected.called_as_of };
}

/**
 * List each state's results page, for the methodology page's credits.
 * @returns Publisher, URL and date checked, keyed by state code in alphabetical order.
 */
export function electedSources(): ElectedFile["sources"] {
  return elected.sources;
}

/**
 * Say when the list of uncalled races was last checked.
 * @returns The time as written in the uncalled list, such as "2026-11-06 09:32 ET".
 */
export function calledAsOf(): string {
  return elected.called_as_of;
}
