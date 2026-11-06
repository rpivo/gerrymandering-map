import { describe, expect, it } from "vitest";

import { getZips, zipLabel, zipSummary, ZIPS_SHOWN_OPEN } from "./zips";

describe("a district's ZIP codes", () => {
  it("writes a whole ZIP code alone and a split one with its share", () => {
    expect(zipLabel({ zip: "78221", share: 1 })).toBe("78221");
    expect(zipLabel({ zip: "78222", share: 0.62 })).toBe("78222 (62%)");
    expect(zipLabel({ zip: "05401", share: 0.01 })).toBe("05401 (1%)");
  });

  it("sums up how many ZIP codes there are and how many are split", () => {
    expect(zipSummary([{ zip: "1", share: 1 }, { zip: "2", share: 0.5 }, { zip: "3", share: 1 }])).toBe(
      "3 ZIP codes have residents in this district. 1 of them is split with another district.",
    );
    expect(zipSummary([{ zip: "1", share: 0.5 }, { zip: "2", share: 0.4 }])).toBe(
      "2 ZIP codes have residents in this district. 2 of them are split with other districts.",
    );
    expect(zipSummary([{ zip: "1", share: 1 }])).toBe(
      "1 ZIP code has residents in this district. It lies wholly within it.",
    );
    expect(zipSummary([{ zip: "1", share: 1 }, { zip: "2", share: 1 }])).toBe(
      "2 ZIP codes have residents in this district. All of them lie wholly within it.",
    );
  });

  it("has ZIP codes for every district, in order, with shares from 0 to 1", () => {
    const zips = getZips("TX-35");
    expect(zips.length).toBeGreaterThan(10); // anchor: real data
    expect(zips.map((z) => z.zip)).toEqual([...zips.map((z) => z.zip)].sort());
    for (const z of zips) {
      expect(z.zip).toMatch(/^\d{5}$/);
      expect(z.share).toBeGreaterThan(0);
      expect(z.share).toBeLessThanOrEqual(1);
    }
    expect(ZIPS_SHOWN_OPEN).toBeGreaterThan(0);
  });
});

describe("a district page's ZIP codes", () => {
  const page = async (id: string) => {
    const { experimental_AstroContainer: AstroContainer } = await import("astro/container");
    const { default: DistrictPage } = await import("../pages/[state]/[district].astro");
    const { getDistrict } = await import("./data");
    const container = await AstroContainer.create();
    return container.renderToString(DistrictPage, { props: { district: getDistrict(id) } });
  };
  const section = (html: string) => {
    const start = html.indexOf('id="zips-heading"');
    expect(start).toBeGreaterThan(-1); // anchor: the section rendered
    return html.slice(start, html.indexOf("</section>", start));
  };

  it("comes right after cities and towns", async () => {
    const html = await page("TX-35");
    const zips = html.indexOf('id="zips-heading"');
    expect(zips).toBeGreaterThan(html.indexOf('id="places-heading"'));
    expect(zips).toBeLessThan(html.indexOf('id="president-heading"'));
  });

  it("lists a short list openly, with split shares and a methodology link", async () => {
    const zips = getZips("NY-09");
    expect(zips.length).toBeLessThanOrEqual(ZIPS_SHOWN_OPEN); // anchor: a short list
    const html = section(await page("NY-09"));
    expect(html).not.toContain("<details");
    for (const z of zips) expect(html).toMatch(new RegExp(`<li[^>]*>${zipLabel(z).replace(/[()]/g, "\\$&")}</li>`));
    expect(html).toContain('href="/methodology#zips"');
  });

  it("puts a long list in a box the reader opens", async () => {
    const n = getZips("WV-01").length;
    expect(n).toBeGreaterThan(ZIPS_SHOWN_OPEN); // anchor: a long list
    const html = section(await page("WV-01"));
    expect(html).toContain("<details");
    expect(html).toContain(`Show all ${n} ZIP codes`);
  });
});
