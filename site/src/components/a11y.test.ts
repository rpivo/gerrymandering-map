import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";

import DistrictShape from "./DistrictShape.astro";
import ScoreBadge from "./ScoreBadge.astro";
import StateMapSvg from "./StateMapSvg.astro";

let container: AstroContainer;

beforeAll(async () => {
  container = await AstroContainer.create();
});

describe("StateMapSvg", () => {
  it("keeps map links out of the tab order, since the districts table has the same links", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "TX", stateName: "Texas" } });
    const links = html.match(/<a\b[^>]*>/g) ?? [];
    // Anchor: Texas has 38 districts, so an empty match can't pass vacuously.
    expect(links).toHaveLength(38);
    expect(links.filter((a) => !a.includes('tabindex="-1"'))).toEqual([]);
  });
});

describe("DistrictShape", () => {
  it("is a labeled image when given a label", async () => {
    const html = await container.renderToString(DistrictShape, {
      props: { outline: { viewBox: "0 0 1 1", d: "M0 0L1 1" }, label: "Outline of TX-35" },
    });
    expect(html).toContain('role="img"');
    expect(html).toContain('aria-label="Outline of TX-35"');
  });

  it("is hidden from screen readers without a label, as inside a card link that already names it", async () => {
    const html = await container.renderToString(DistrictShape, {
      props: { outline: { viewBox: "0 0 1 1", d: "M0 0L1 1" } },
    });
    expect(html).toContain('aria-hidden="true"');
    expect(html).not.toContain('role="img"');
  });
});

describe("ScoreBadge", () => {
  it("says what the number is to screen readers", async () => {
    const html = await container.renderToString(ScoreBadge, { props: { score: 85 } });
    // Screen readers join inline text without spaces, so the words need their own.
    const text = html.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
    expect(text).toBe("Irregularity score 85 Very irregular");
  });
});
