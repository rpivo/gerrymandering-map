import { describe, expect, it } from "vitest";

import { states } from "./data";
import { MIN_DISTRICTS, fairness, getFairness, leanText, unscoredReason, voteSummary, type Fairness } from "./fairness";

const scored: Fairness = {
  state: "NC",
  status: "scored",
  districts: 14,
  dem_vote_share: 0.4837,
  dem_seats: 3,
  one_party_won_every_district: false,
  efficiency_gap: 0.2573,
  mean_median: 0.058,
  declination: 0.5792,
  method: "official report",
};

const unscored = (status: Fairness["status"]): Fairness => ({
  ...scored,
  status,
  districts: null,
  dem_vote_share: null,
  dem_seats: null,
  one_party_won_every_district: null,
  efficiency_gap: null,
  mean_median: null,
  declination: null,
  method: null,
});

describe("the fairness data", () => {
  it("has a record for every state", () => {
    expect(fairness).toHaveLength(50);
    expect(new Set(fairness.map((f) => f.state))).toEqual(new Set(states.map((s) => s.state)));
  });

  it("has every score for every scored state, and only declination missing after a sweep", () => {
    const withScores = fairness.filter((f) => f.status === "scored");
    expect(withScores.length).toBeGreaterThanOrEqual(28); // anchor: the loop checks something
    for (const f of withScores) {
      expect(f.efficiency_gap).not.toBeNull();
      expect(f.mean_median).not.toBeNull();
      expect(f.declination === null).toBe(f.one_party_won_every_district);
    }
  });

  it("agrees with the pipeline on the smallest state it scores", () => {
    const seats = new Map(states.map((s) => [s.state, s.seats]));
    const tooFew = fairness.filter((f) => f.status === "too_few_districts");
    expect(tooFew.length).toBeGreaterThan(0); // anchor
    expect(Math.max(...tooFew.map((f) => seats.get(f.state) ?? 0))).toBe(MIN_DISTRICTS - 1);
    const scoredSizes = fairness.filter((f) => f.status === "scored").map((f) => f.districts ?? 0);
    expect(Math.min(...scoredSizes)).toBe(MIN_DISTRICTS);
  });

  it("finds a state by its code, and throws for an unknown one", () => {
    expect(getFairness("NC").status).toBe("scored");
    expect(() => getFairness("ZZ")).toThrow("ZZ");
  });
});

describe("leanText", () => {
  it.each([
    [0.2573, 3, "Favors Republicans"],
    [-0.184, 3, "Favors Democrats"],
    [0.0004, 3, "Neutral"],
    [-0.0004, 3, "Neutral"],
    [0, 2, "Neutral"],
    [0.004, 2, "Neutral"],
    [0.006, 2, "Favors Republicans"],
  ])("%f shown to %i places is %s", (value, places, expected) => {
    expect(leanText(value, places)).toBe(expected);
  });
});

describe("voteSummary", () => {
  it("gives the vote share and seats carried", () => {
    expect(voteSummary(scored)).toBe(
      "Kamala Harris (Democrat) won 48.4% of the two-party vote and carried 3 of 14 districts.",
    );
  });

  it("says when the Republican carried every district", () => {
    const ar = { ...scored, districts: 4, dem_vote_share: 0.3433, dem_seats: 0, one_party_won_every_district: true };
    expect(voteSummary(ar)).toBe(
      "Kamala Harris (Democrat) won 34.3% of the two-party vote. Donald Trump (Republican) carried all 4 districts.",
    );
  });

  it("says when the Democrat carried every district", () => {
    const ct = { ...scored, districts: 5, dem_vote_share: 0.5738, dem_seats: 5, one_party_won_every_district: true };
    expect(voteSummary(ct)).toBe(
      "Kamala Harris (Democrat) won 57.4% of the two-party vote and carried all 5 districts.",
    );
  });

  it("throws for a state without scores", () => {
    expect(() => voteSummary(unscored("at_large"))).toThrow();
  });
});

describe("unscoredReason", () => {
  it("explains an at-large state", () => {
    expect(unscoredReason(unscored("at_large"), 1)).toContain("no lines to score");
  });

  it("explains too few districts, with the count", () => {
    expect(unscoredReason(unscored("too_few_districts"), 2)).toContain("only 2 districts");
    expect(unscoredReason(unscored("too_few_districts"), 3)).toContain("4 or more");
  });

  it("explains a map redrawn for 2026", () => {
    expect(unscoredReason(unscored("awaiting_2026_results"), 7)).toContain("2026 House results");
  });

  it("has a fallback for missing vote data", () => {
    expect(unscoredReason(unscored("no_vote_data"), 8)).toContain("vote data");
  });

  it("throws for a scored state", () => {
    expect(() => unscoredReason(scored, 14)).toThrow();
  });
});
