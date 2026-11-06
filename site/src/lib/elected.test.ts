import { describe, expect, it } from "vitest";

import { houseLines, isSamePerson, seatOnBallot, senateBallotLine, type Outcome } from "./elected";

const won: Outcome = { status: "elected", name: "Janet Mills", party: "Democrat" };

describe("the House race line", () => {
  it("names the winner and when they take office", () => {
    expect(houseLines(won)).toEqual({
      winner: "Janet Mills, Democrat",
      detail: "Elected November 3, 2026, takes office January 3, 2027.",
    });
  });

  it("names nobody while the race is uncalled", () => {
    expect(houseLines({ status: "uncalled" })).toEqual({
      winner: undefined,
      detail: "The November 3, 2026 race hasn't been called yet.",
    });
  });

  it("says when the state hasn't published results to read yet", () => {
    expect(houseLines({ status: "pending" }, "Michigan")).toEqual({
      winner: undefined,
      detail: "Statewide results from Michigan for the November 3, 2026 election aren't available yet.",
    });
  });

  it("gives a runoff's date in words", () => {
    expect(houseLines({ status: "runoff", runoff_date: "2026-12-12" }).detail).toBe(
      "No candidate won a majority on November 3, 2026, so the race goes to a runoff on December 12, 2026.",
    );
  });
});

describe("a senator's seat on the 2026 ballot", () => {
  it("maps class 2 to the regular race and class 3 to a special one", () => {
    expect(seatOnBallot(2)).toBe("regular");
    expect(seatOnBallot(3)).toBe("special");
    expect(seatOnBallot(1)).toBeUndefined();
  });

  it("matches a winner to the senator by last name, ignoring suffixes and case", () => {
    expect(isSamePerson("King", "ANGUS KING JR.")).toBe(true);
    expect(isSamePerson("Collins", "Susan Collins")).toBe(true);
    expect(isSamePerson("Collins", "Janet Mills")).toBe(false);
  });

  it("says a senator was re-elected, or who won the seat", () => {
    expect(senateBallotLine("Collins", { ...won, name: "Susan Collins", party: "Republican" })).toBe(
      "Re-elected November 3, 2026.",
    );
    expect(senateBallotLine("Collins", won)).toBe(
      "Seat on the November 3, 2026 ballot: Janet Mills, Democrat, won and takes office January 3, 2027.",
    );
    expect(senateBallotLine("Capito", { status: "pending" })).toBe(
      "Seat on the November 3, 2026 ballot: results aren't available yet.",
    );
    expect(senateBallotLine("Hyde-Smith", { status: "uncalled" })).toBe(
      "Seat on the November 3, 2026 ballot: the race hasn't been called yet.",
    );
  });
});
