import { describe, expect, it } from "vitest";

import { districtPath, parseDistrictId } from "./districts";

describe("parseDistrictId", () => {
  it("parses a numbered district", () => {
    expect(parseDistrictId("TX-35")).toEqual({ state: "TX", number: 35 });
  });

  it("parses single-digit districts written with a leading zero", () => {
    expect(parseDistrictId("CA-07")).toEqual({ state: "CA", number: 7 });
  });

  it("parses an at-large district as having no number", () => {
    expect(parseDistrictId("WY-AL")).toEqual({ state: "WY", number: null });
  });

  it.each(["tx-35", "TX35", "TX-", "TX-0", "TX-AB", "TEX-1", "TX-1-2", ""])(
    "rejects %j",
    (id) => {
      expect(() => parseDistrictId(id)).toThrow(/district id/i);
    },
  );
});

describe("districtPath", () => {
  it("builds a lowercase state/number path", () => {
    expect(districtPath("TX-35")).toBe("/tx/35");
  });

  it("drops the leading zero", () => {
    expect(districtPath("CA-07")).toBe("/ca/7");
  });

  it("uses al for at-large districts", () => {
    expect(districtPath("WY-AL")).toBe("/wy/al");
  });
});
