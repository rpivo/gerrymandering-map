import { describe, expect, it } from "vitest";

import { closeupFor, closeups } from "./closeups";
import { districtsInState, states } from "./data";

describe("closeups", () => {
  it("names every close-up after the biggest city in it", () => {
    const all = states.flatMap((s) => closeups(s.state));
    expect(all).toHaveLength(31); // anchor: every close-up the pipeline found
    expect(all.filter((c) => !/ area(, closer in)?$/.test(c.name))).toEqual([]);
  });

  it("finds Los Angeles, closer in again, and the Bay Area in California, biggest first", () => {
    expect(closeups("CA").map((c) => c.name)).toEqual([
      "Los Angeles area",
      "Los Angeles area, closer in",
      "San Jose area",
      "Fresno area",
    ]);
  });

  it("puts each nested close-up right after its parent, inside the parent's drawing", () => {
    const nested = states.flatMap((s) => closeups(s.state).map((c, i, all) => ({ c, i, all })).filter(({ c }) => c.parent !== undefined));
    expect(nested.map(({ c }) => c.name)).toEqual([
      "Los Angeles area, closer in",
      "New York area, closer in",
      "Houston area, closer in",
    ]);
    for (const { c, i, all } of nested) {
      expect(c.parent).toBe(i - 1);
      const [, , w, h] = (all[i - 1]?.viewBox ?? "").split(" ").map(Number) as [number, number, number, number];
      const [x0, y0, x1, y1] = c.box;
      expect(x0 >= 0 && y0 >= 0 && x1 <= w && y1 <= h).toBe(true);
    }
  });

  it("gives a nested close-up's enlargement from the state map, not from its parent", () => {
    const [la, central] = closeups("CA");
    const [x0, , x1] = central?.box ?? [];
    expect(central?.zoom).toBeCloseTo((la?.zoom ?? 0) * (1000 / ((x1 ?? 0) - (x0 ?? 0))), 5);
    expect(central?.zoom).toBeGreaterThan(5);
  });

  it("has none for a state whose districts are all big enough to see", () => {
    expect(closeups("WY")).toEqual([]);
    expect(closeups("KS")).toEqual([]);
  });

  it("gives how much each close-up enlarges the map", () => {
    const [la] = closeups("CA");
    expect(la?.zoom).toBeCloseTo(1000 / 329, 1);
  });
});

describe("closeupFor", () => {
  it("finds the closest close-up a district lies wholly inside", () => {
    expect(closeupFor("CA-34")?.name).toBe("Los Angeles area, closer in");
    expect(closeupFor("CA-48")?.name).toBe("Los Angeles area");
  });

  it("finds none for a district outside every close-up", () => {
    expect(closeupFor("CA-01")).toBeUndefined();
  });

  it("finds none for a big district only partly inside a close-up", () => {
    // Every district drawn in a close-up but not wholly inside it is one of these.
    const partly = districtsInState("CA").filter(
      (d) => closeups("CA").some((c) => d.id in c.paths) && closeupFor(d.id) === undefined,
    );
    expect(partly.length).toBeGreaterThan(0); // anchor: some big neighbors are cut by boxes
    expect(partly.map((d) => d.id)).not.toContain("CA-34");
  });
});
