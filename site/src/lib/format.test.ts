import { describe, expect, it } from "vitest";

import { sources } from "./data";
import { districtTitle, lessCompactThan, measurePercentileText, ordinal, scoreBand, sourceNote } from "./format";

describe("ordinal", () => {
  it.each([
    [1, "1st"],
    [2, "2nd"],
    [3, "3rd"],
    [4, "4th"],
    [11, "11th"],
    [12, "12th"],
    [13, "13th"],
    [21, "21st"],
    [22, "22nd"],
    [23, "23rd"],
    [101, "101st"],
    [111, "111th"],
  ])("%i is %s", (n, expected) => {
    expect(ordinal(n)).toBe(expected);
  });
});

describe("districtTitle", () => {
  it("names a numbered district", () => {
    expect(districtTitle("Texas", 35)).toBe("Texas District 35");
  });

  it("names an at-large district", () => {
    expect(districtTitle("Wyoming", null)).toBe("Wyoming At-Large District");
  });
});

describe("lessCompactThan", () => {
  it("is 100 for the most irregular district", () => {
    expect(lessCompactThan(1, 429)).toBe(100);
  });

  it("is 0 for the most compact district", () => {
    expect(lessCompactThan(429, 429)).toBe(0);
  });

  it("rounds to a whole percent in between", () => {
    expect(lessCompactThan(12, 429)).toBe(97);
    expect(lessCompactThan(215, 429)).toBe(50);
  });

  it("rejects ranks outside 1..total", () => {
    expect(() => lessCompactThan(0, 429)).toThrow(/rank/i);
    expect(() => lessCompactThan(430, 429)).toThrow(/rank/i);
  });
});

describe("scoreBand", () => {
  it.each([
    [0, "very-compact", "Very compact"],
    [19, "very-compact", "Very compact"],
    [20, "compact", "Compact"],
    [40, "middle", "Middle of the pack"],
    [60, "irregular", "Irregular"],
    [80, "very-irregular", "Very irregular"],
    [100, "very-irregular", "Very irregular"],
  ])("%i is %s", (score, key, label) => {
    expect(scoreBand(score)).toEqual({ key, label });
  });

  it("rejects scores outside 0..100", () => {
    expect(() => scoreBand(-1)).toThrow(/score/i);
    expect(() => scoreBand(101)).toThrow(/score/i);
  });
});

describe("measurePercentileText", () => {
  it("states the percentile in words", () => {
    expect(measurePercentileText(63.4)).toBe("at least as compact as 63% of districts on this measure");
  });

  it("describes the very lowest without saying 0%", () => {
    expect(measurePercentileText(0.2)).toBe("among the least compact 1% of districts on this measure");
  });

  it("calls the very top the most compact", () => {
    expect(measurePercentileText(100)).toBe("the most compact district on this measure");
  });
});

describe("sourceNote", () => {
  it("ends the description with one period, even when it already has one", () => {
    expect(sourceNote("Congress Act 2 (SB 121), 2026 Regular Session. Page: https://x.gov", "No license stated", "2026-11-04")).toBe(
      "Congress Act 2 (SB 121), 2026 Regular Session. No license stated. Downloaded 2026-11-04.",
    );
  });

  it("adds the period when the description has none", () => {
    expect(sourceNote("TIGER/Line 2020 blocks", "Public domain (U.S. Government work)", "2026-11-04")).toBe(
      "TIGER/Line 2020 blocks. Public domain (U.S. Government work). Downloaded 2026-11-04.",
    );
  });

  it("never doubles a period for any source the site lists", () => {
    // Anchor: the site credits a dozen boundary sources, so an empty list can't pass.
    const notes = sources.filter((s) => s.role === "boundaries").map((s) => sourceNote(s.description, s.license, s.downloaded));
    expect(notes.length).toBeGreaterThan(10);
    expect(notes.filter((n) => n.includes(".."))).toEqual([]);
  });
});
