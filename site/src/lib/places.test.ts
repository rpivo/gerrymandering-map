import { describe, expect, it } from "vitest";

import { districts } from "./data";
import { getPlaces, outsidePlacesText, placeCountText, type Place } from "./places";

describe("placeCountText", () => {
  it("says a place is wholly in the district", () => {
    const p: Place = { name: "Metairie", kind: "community", pop: 143507, place_pop: 143507 };
    expect(placeCountText(p)).toBe("all 143,507 residents");
  });

  it("says how much of a split place is in the district", () => {
    const p: Place = { name: "Baton Rouge", kind: "city", pop: 155032, place_pop: 227470 };
    expect(placeCountText(p)).toBe("155,032 of its 227,470 residents");
  });

  it("says when a place has only one resident here", () => {
    const p: Place = { name: "Tiny", kind: "town", pop: 1, place_pop: 40 };
    expect(placeCountText(p)).toBe("1 of its 40 residents");
  });
});

describe("outsidePlacesText", () => {
  it("gives the share of the district outside any place", () => {
    expect(outsidePlacesText(0.69)).toBe(
      "31% of this district's people live outside any city, town or named community.",
    );
  });

  it("says nothing when nearly everyone lives in a place", () => {
    expect(outsidePlacesText(0.996)).toBeNull();
  });

  it("never rounds a real share outside down to 0% or everyone to 100%", () => {
    expect(outsidePlacesText(0.992)).toContain("1%");
    expect(outsidePlacesText(0.001)).toContain("99%");
  });
});

describe("getPlaces", () => {
  it("has a record for every district", () => {
    // Anchor: 435 districts, so a missing data file can't pass vacuously.
    expect(districts).toHaveLength(435);
    expect(districts.filter((d) => !getPlaces(d.id))).toEqual([]);
  });

  it("lists New Orleans in the district that holds most of it", () => {
    const names = getPlaces("LA-02").places.map((p) => p.name);
    expect(names[0]).toBe("New Orleans");
  });

  it("refuses an unknown district", () => {
    expect(() => getPlaces("ZZ-99")).toThrow();
  });
});
