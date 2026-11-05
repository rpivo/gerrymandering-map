import { describe, expect, it } from "vitest";

import { districts } from "./data";
import { getPopulation, population, populationText, type Population } from "./population";

const base: Population = {
  id: "XX-01",
  vap: 1000,
  hispanic: 0.05,
  white: 0.8,
  black: 0.1,
  aian: 0.01,
  asian: 0.03,
  nhpi: 0.001,
  minority: 0.2,
  majority: null,
};

describe("the population data", () => {
  it("has a record for every district, and 117 majority-minority ones", () => {
    expect(new Set(population.map((p) => p.id))).toEqual(new Set(districts.map((d) => d.id)));
    expect(population.filter((p) => p.majority !== null)).toHaveLength(117);
  });

  it("names a majority only when the shares say so", () => {
    expect(population.length).toBe(435); // anchor
    for (const p of population) {
      if (p.majority === null) {
        expect(p.minority).toBeLessThanOrEqual(0.5);
      } else if (p.majority === "coalition") {
        expect(p.minority).toBeGreaterThan(0.5);
      } else {
        expect(p[p.majority]).toBeGreaterThan(0.5);
      }
    }
  });

  it("finds a district, and throws for an unknown one", () => {
    expect(getPopulation("AL-07").majority).toBe("black");
    expect(() => getPopulation("ZZ-01")).toThrow("ZZ-01");
  });
});

describe("populationText", () => {
  it("names a single majority group with its share", () => {
    const p: Population = { ...base, black: 0.504, white: 0.43, minority: 0.573, majority: "black" };
    expect(populationText(p)).toBe("Most of this district's voting-age residents are Black (50.4%).");
  });

  it("uses the Census name for Hispanic residents", () => {
    const p: Population = { ...base, hispanic: 0.616, minority: 0.876, majority: "hispanic" };
    expect(populationText(p)).toBe(
      "Most of this district's voting-age residents are Hispanic or Latino (61.6%).",
    );
  });

  it("gives the minority total and the largest groups for a coalition", () => {
    const p: Population = {
      ...base,
      hispanic: 0.367,
      black: 0.1,
      asian: 0.125,
      aian: 0.005,
      minority: 0.583,
      majority: "coalition",
    };
    expect(populationText(p)).toBe(
      "Most of this district's voting-age residents (58.3%) belong to minority groups. The largest are Hispanic or Latino (36.7%), Asian (12.5%) and Black (10.0%).",
    );
  });

  it("names one group when only one is large", () => {
    const p: Population = { ...base, hispanic: 0.45, black: 0.04, asian: 0.04, minority: 0.53, majority: "coalition" };
    expect(populationText(p)).toBe(
      "Most of this district's voting-age residents (53.0%) belong to minority groups. The largest is Hispanic or Latino (45.0%).",
    );
  });

  it("says nothing for a district without a minority majority", () => {
    expect(populationText(base)).toBeNull();
  });
});
