import { describe, expect, it } from "vitest";

import type { District, StateInfo } from "./data";
import { getDistrict, getState } from "./data";
import { pathBounds, tipPlacement, tooltipLines } from "./tooltip";

describe("pathBounds", () => {
  it("finds the box around every point of every ring", () => {
    expect(pathBounds("M10 20L30 20L30 50ZM5 40L8 60Z")).toEqual({ minX: 5, minY: 20, maxX: 30, maxY: 60 });
  });

  it("handles negative and decimal coordinates", () => {
    expect(pathBounds("M-1.5 2L3 -4.25Z")).toEqual({ minX: -1.5, minY: -4.25, maxX: 3, maxY: 2 });
  });

  it("refuses a path with no points", () => {
    expect(() => pathBounds("")).toThrow();
  });
});

describe("tipPlacement", () => {
  const viewBox = "0 0 100 200";

  it("goes above a district low on the map, as a share of the map", () => {
    const p = tipPlacement({ minX: 40, minY: 120, maxX: 60, maxY: 180 }, viewBox);
    expect(p).toEqual({ x: 50, y: 60, side: "above", align: "center" });
  });

  it("goes below a district high on the map", () => {
    const p = tipPlacement({ minX: 40, minY: 10, maxX: 60, maxY: 50 }, viewBox);
    expect(p).toEqual({ x: 50, y: 25, side: "below", align: "center" });
  });

  it("lines up with the near edge for districts at the sides, so it stays on the map", () => {
    expect(tipPlacement({ minX: 0, minY: 150, maxX: 20, maxY: 160 }, viewBox).align).toBe("start");
    expect(tipPlacement({ minX: 80, minY: 150, maxX: 100, maxY: 160 }, viewBox).align).toBe("end");
  });

  it("sits over the middle of a district that fills the map, like an at-large state", () => {
    const p = tipPlacement({ minX: 0, minY: 0, maxX: 100, maxY: 200 }, viewBox);
    expect(p).toEqual({ x: 50, y: 50, side: "over", align: "center" });
  });

  it("accounts for a viewBox that doesn't start at 0", () => {
    const p = tipPlacement({ minX: 140, minY: 220, maxX: 160, maxY: 280 }, "100 100 100 200");
    expect(p).toEqual({ x: 50, y: 60, side: "above", align: "center" });
  });
});

describe("tooltipLines", () => {
  const base: District = {
    ...getDistrict("IL-15"),
    irregularity: 74,
    rank_national: 40,
    rank_state: 3,
    state_edge_share: 0,
    redrawn_2026: false,
    at_large: false,
  };
  const illinois: StateInfo = { ...getState("IL"), seats: 17 };

  it("leads with the score and both ranks", () => {
    const tip = tooltipLines(base, illinois, null);
    expect(tip.heading).toBe("IL-15");
    expect(tip.lines).toEqual([
      "Irregularity score 74",
      expect.stringMatching(/^Less compact than \d+% of districts$/),
      "3rd least compact of 17 in Illinois",
    ]);
    expect(tip.notes).toEqual([]);
  });

  it("adds a short note for each piece of context that applies", () => {
    const tip = tooltipLines({ ...base, state_edge_share: 0.42, redrawn_2026: true }, illinois, "black");
    expect(tip.notes).toEqual([
      "42% of its border is the state's edge",
      "Majority-minority (2020 voting-age population)",
      "New lines for 2026",
    ]);
  });

  it("leaves out a small state edge, which barely touches the score, and keeps one from 10% up", () => {
    expect(tooltipLines({ ...base, state_edge_share: 0.094 }, illinois, null).notes).toEqual([]);
    expect(tooltipLines({ ...base, state_edge_share: 0.1 }, illinois, null).notes).toEqual([
      "10% of its border is the state's edge",
    ]);
  });

  it("explains an at-large district instead of scoring it", () => {
    const wyoming = getState("WY");
    const tip = tooltipLines(getDistrict("WY-AL"), wyoming, null);
    expect(tip.lines).toEqual(["One district covers the whole state, so it isn't scored"]);
    // The state's edge is the whole border of an at-large district, so it says nothing new.
    expect(tip.notes).toEqual([]);
  });
});
