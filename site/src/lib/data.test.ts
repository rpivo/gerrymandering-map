import { describe, expect, it } from "vitest";

import {
  adjacent,
  districts,
  districtsInState,
  getDistrict,
  getState,
  outline,
  rankedCount,
  sources,
  stateMap,
  states,
} from "./data";

describe("drawing notes", () => {
  it("note what Hawaii's drawings leave out, and nothing else", async () => {
    const { shapeNote } = await import("./data");
    expect(shapeNote("HI-02")).toBe("The Northwestern Hawaiian Islands, part of District 2, are not shown.");
    expect(stateMap("HI").note).toBe(shapeNote("HI-02"));
    expect(districts.filter((d) => shapeNote(d.id) !== null).map((d) => d.id)).toEqual(["HI-02"]);
    expect(states.filter((s) => stateMap(s.state).note !== undefined).map((s) => s.state)).toEqual(["HI"]);
  });
});

describe("the generated data", () => {
  it("has every district and state", () => {
    expect(districts).toHaveLength(435);
    expect(states).toHaveLength(50);
    expect(rankedCount).toBe(429);
  });

  it("has a card and page outline for every district", () => {
    expect(districts).toHaveLength(435); // so the loop can't pass by checking nothing
    for (const district of districts) {
      for (const kind of ["card", "page"] as const) {
        const shape = outline(district.id, kind);
        expect(shape.d.startsWith("M")).toBe(true);
        expect(shape.viewBox).toMatch(/^0 0 \d+ \d+$/);
      }
    }
  });

  it("has a state map path for every district in each state", () => {
    expect(states).toHaveLength(50);
    for (const state of states) {
      const ids = districtsInState(state.state).map((d) => d.id);
      expect(Object.keys(stateMap(state.state).paths).sort()).toEqual(ids.sort());
    }
  });

  it("lists sources, including the Census boundaries", () => {
    expect(sources.some((s) => s.id === "census-cd119-cb-2025-500k")).toBe(true);
  });
});

describe("districtsInState", () => {
  it("returns a state's districts in number order", () => {
    const texas = districtsInState("TX");
    expect(texas).toHaveLength(38);
    expect(texas.map((d) => d.number)).toEqual(Array.from({ length: 38 }, (_, i) => i + 1));
  });
});

describe("getDistrict and getState", () => {
  it("find by ID", () => {
    expect(getDistrict("TX-35").state).toBe("TX");
    expect(getState("TX").name).toBe("Texas");
  });

  it("throw for unknown IDs", () => {
    expect(() => getDistrict("TX-99")).toThrow(/unknown district: TX-99/i);
    expect(() => getState("DC")).toThrow(/unknown state: DC/i);
  });
});

describe("adjacent", () => {
  it("links to the previous and next district in the state", () => {
    expect(adjacent("TX-35")).toEqual({ previous: "TX-34", next: "TX-36" });
  });

  it("has no previous for the first district, and no next for the last", () => {
    expect(adjacent("TX-01").previous).toBeNull();
    expect(adjacent("TX-38").next).toBeNull();
  });

  it("has neither for an at-large district", () => {
    expect(adjacent("WY-AL")).toEqual({ previous: null, next: null });
  });
});
