import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it } from "vitest";

import DistrictPage from "../pages/[state]/[district].astro";
import { getDistrict } from "./data";

async function render(id: string): Promise<string> {
  const container = await AstroContainer.create();
  return container.renderToString(DistrictPage, { props: { district: getDistrict(id) } });
}

describe("a district page's state map", () => {
  it("has the score color legend, since the map is colored by score", async () => {
    const html = await render("LA-02");
    const map = html.slice(html.indexOf('id="state-heading"'));
    expect(map).toMatch(/class="state-map\b/); // anchor: the map section rendered
    expect(map).toContain('aria-label="Irregularity score colors"');
  });

  it("has no legend for an at-large state, whose one district isn't scored", async () => {
    const html = await render("WY-AL");
    expect(html).toMatch(/class="state-map\b/);
    expect(html).not.toContain('aria-label="Irregularity score colors"');
  });
});
