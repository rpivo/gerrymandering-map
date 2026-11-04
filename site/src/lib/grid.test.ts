import { describe, expect, it } from "vitest";

import { type Card, matches, normalizeQuery, sortCards } from "./grid";

const card = (id: string, stateName: string, score: number | null, rank: number | null): Card => ({
  id,
  state: id.slice(0, 2),
  stateName,
  number: id.endsWith("AL") ? null : Number(id.slice(3)),
  score,
  rank,
});

const TX35 = card("TX-35", "Texas", 47, 226);
const TX01 = card("TX-01", "Texas", 38, 283);
const LA02 = card("LA-02", "Louisiana", 99, 1);
const WYAL = card("WY-AL", "Wyoming", null, null);
const ALL = [TX35, TX01, LA02, WYAL];

describe("normalizeQuery", () => {
  it("lowercases and drops spaces and hyphens", () => {
    expect(normalizeQuery(" TX - 35 ")).toBe("tx35");
  });
});

describe("matches", () => {
  const filters = { query: "", state: "", includeAtLarge: true };

  it("matches everything with no filters", () => {
    expect(ALL.filter((c) => matches(c, filters))).toHaveLength(4);
  });

  it.each(["TX-35", "tx35", "tx 35", "Tx-35"])("finds a district by ID written as %j", (query) => {
    expect(ALL.filter((c) => matches(c, { ...filters, query }))).toEqual([TX35]);
  });

  it("finds a district written with or without the leading zero", () => {
    expect(ALL.filter((c) => matches(c, { ...filters, query: "TX-01" }))).toEqual([TX01]);
    expect(ALL.filter((c) => matches(c, { ...filters, query: "tx-1" }))).toEqual([TX01]);
  });

  it("matches IDs exactly, so TX-3 doesn't find TX-35", () => {
    expect(ALL.filter((c) => matches(c, { ...filters, query: "tx3" }))).toEqual([]);
  });

  it("finds a state's districts by name or code", () => {
    expect(ALL.filter((c) => matches(c, { ...filters, query: "texas" }))).toEqual([TX35, TX01]);
    expect(ALL.filter((c) => matches(c, { ...filters, query: "TX" }))).toEqual([TX35, TX01]);
  });

  it("matches partial state names", () => {
    expect(ALL.filter((c) => matches(c, { ...filters, query: "louis" }))).toEqual([LA02]);
  });

  it("filters by state", () => {
    expect(ALL.filter((c) => matches(c, { ...filters, state: "LA" }))).toEqual([LA02]);
  });

  it("can hide at-large districts", () => {
    expect(ALL.filter((c) => matches(c, { ...filters, includeAtLarge: false }))).not.toContain(WYAL);
  });
});

describe("sortCards", () => {
  it("puts the most irregular first, at-large last", () => {
    expect(sortCards(ALL, "irregular").map((c) => c.id)).toEqual(["LA-02", "TX-35", "TX-01", "WY-AL"]);
  });

  it("puts the most compact first, at-large last", () => {
    expect(sortCards(ALL, "compact").map((c) => c.id)).toEqual(["TX-01", "TX-35", "LA-02", "WY-AL"]);
  });

  it("sorts by state name, then district number", () => {
    expect(sortCards(ALL, "state").map((c) => c.id)).toEqual(["LA-02", "TX-01", "TX-35", "WY-AL"]);
  });

  it("does not change the input", () => {
    const input = [...ALL];
    sortCards(input, "compact");
    expect(input).toEqual(ALL);
  });
});
