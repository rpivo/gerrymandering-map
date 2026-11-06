import { describe, expect, it } from "vitest";

import { type Card, matches } from "./grid";
import { getZips } from "./zips";
import { zipIndex, zipMessage, zipPrefix, zipQuery } from "./zip-search";

const card = (id: string, number: number | null): Card => ({
  id,
  state: id.slice(0, 2),
  stateName: "",
  number,
  score: null,
  rank: null,
});

describe("a ZIP code query", () => {
  it("is five digits, with spaces allowed around it", () => {
    expect(zipQuery(" 78221 ")).toBe("78221");
    expect(zipQuery("7822")).toBeUndefined();
    expect(zipQuery("TX-35")).toBeUndefined();
    expect(zipQuery("782211")).toBeUndefined();
  });

  it("is looked up in the file for its first three digits", () => {
    expect(zipPrefix("05401")).toBe("054");
  });
});

describe("the ZIP index", () => {
  it("groups ZIP codes by their first three digits, with each district's percent", () => {
    const tx35 = getZips("TX-35").find((z) => z.share < 1);
    if (!tx35) throw new Error("TX-35 should have a split ZIP code"); // anchor
    const entry = zipIndex().get(zipPrefix(tx35.zip))?.[tx35.zip] ?? [];
    expect(entry).toContainEqual(["TX-35", Math.round(tx35.share * 100)]);
    expect(entry.length).toBeGreaterThan(1);
  });

  it("lists the district with the most of a split ZIP code's residents first", () => {
    for (const entries of zipIndex().values()) {
      for (const list of Object.values(entries)) {
        const pcts = list.map(([, pct]) => pct);
        expect(pcts).toEqual([...pcts].sort((a, b) => b - a));
      }
    }
  });
});

describe("matching cards to a ZIP code", () => {
  const filters = { query: "82001", state: "", includeAtLarge: false };

  it("shows exactly the ZIP code's districts, even at-large ones the box would hide", () => {
    const zipDistricts = ["WY-AL"];
    expect(matches(card("WY-AL", null), { ...filters, zipDistricts })).toBe(true);
    expect(matches(card("TX-35", 35), { ...filters, zipDistricts })).toBe(false);
  });

  it("shows nothing for a ZIP code with no districts", () => {
    expect(matches(card("TX-35", 35), { ...filters, zipDistricts: [] })).toBe(false);
  });
});

describe("the message for a ZIP code search", () => {
  it("names a whole ZIP code's district", () => {
    expect(zipMessage("78221", [["TX-35", 100]])).toBe("ZIP code 78221 is in TX-35.");
  });

  it("names every district of a split ZIP code, with its share", () => {
    expect(zipMessage("78222", [["TX-35", 62], ["TX-20", 38]])).toBe(
      "ZIP code 78222 is split between TX-35 (62% of its residents) and TX-20 (38%).",
    );
    expect(zipMessage("10001", [["NY-12", 50], ["NY-10", 30], ["NY-13", 20]])).toBe(
      "ZIP code 10001 is split between NY-12 (50% of its residents), NY-10 (30%) and NY-13 (20%).",
    );
  });

  it("explains a ZIP code it can't find", () => {
    expect(zipMessage("00000", undefined)).toBe(
      "No district found for ZIP code 00000. ZIP codes used only for PO boxes or a single organization aren't listed. Try your city or state instead.",
    );
  });
});

describe("the ZIP index files", () => {
  it("are one file per first three digits, holding that group's ZIP codes", async () => {
    const { getStaticPaths, GET } = await import("../pages/zip/[prefix].json");
    const paths = getStaticPaths();
    expect(paths.length).toBe(zipIndex().size);
    expect(paths.length).toBeGreaterThan(800); // anchor: about 900 groups nationally
    const props = paths.find((p) => p.params.prefix === "782")?.props;
    const response = await GET({ params: { prefix: "782" }, props } as never);
    const body = (await response.json()) as Record<string, [string, number][]>;
    expect(Object.keys(body).every((zip) => zip.startsWith("782"))).toBe(true);
    expect(body).toEqual(zipIndex().get("782"));
  });
});
