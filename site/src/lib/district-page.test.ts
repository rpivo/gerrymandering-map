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

describe("a district page's places", () => {
  it("lists the largest places, just before the state map", async () => {
    const html = await render("LA-02");
    const section = html.indexOf('id="places-heading"');
    // Anchor: the section exists, so the order check below can't pass on a missing one.
    expect(section).toBeGreaterThan(-1);
    expect(section).toBeLessThan(html.indexOf('id="state-heading"'));
    const text = html.slice(section).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
    expect(text).toMatch(/New Orleans city [\d,]+ of its [\d,]+ residents/);
  });

  it("points to the methodology page for how places are counted", async () => {
    const html = await render("LA-02");
    const section = html.slice(html.indexOf('id="places-heading"'), html.indexOf('id="state-heading"'));
    expect(section).toContain('href="/methodology#places"');
  });
});

describe("a district page's outline", () => {
  it("marks the district's own cities, apart from the state map's marks", async () => {
    const html = await render("LA-02");
    const top = html.slice(0, html.indexOf('id="state-heading"'));
    expect(top).toMatch(/class="cities district-tier-0/);
    expect(top).toContain(">New Orleans</text>");
    // The state map below keeps its own tiers.
    expect(html.slice(html.indexOf('id="state-heading"'))).toMatch(/class="cities state-tier-0/);
  });
});

describe("a district page's 2024 presidential vote", () => {
  const section = async (id: string) => {
    const html = await render(id);
    const start = html.indexOf('id="president-heading"');
    expect(start).toBeGreaterThan(-1); // anchor: every district has the section
    expect(start).toBeLessThan(html.indexOf('id="state-heading"'));
    const end = html.indexOf("</section>", start);
    return {
      html: html.slice(start, end),
      text: html
        .slice(start, end)
        .replace(/<[^>]+>/g, " ")
        .replace(/&#39;/g, "'")
        .replace(/\s+/g, " "),
    };
  };

  it("gives both candidates' shares, added up from precincts where the lines didn't change", async () => {
    const { text, html } = await section("NE-02");
    expect(text).toContain("Kamala Harris 52.3%");
    expect(text).toContain("Donald Trump 47.7%");
    expect(text).toContain("added up from precinct results");
    expect(html).toContain('href="/methodology#votes"');
  });

  it("uses the state's own report for a redrawn district it published results for", async () => {
    const { text } = await section("TX-35");
    expect(text).toContain("Kamala Harris 44.7%");
    expect(text).toContain("Texas published 2024 results on its 2026 lines");
    expect(text).not.toContain("precinct");
  });

  it("gives the whole state's vote for an at-large district", async () => {
    const { text } = await section("AK-AL");
    expect(text).toContain("Kamala Harris 43.2%");
    expect(text).toContain("the whole state's vote");
  });

  it("says no results exist yet for a redrawn district without any", async () => {
    const { text } = await section("CA-34");
    expect(text).not.toMatch(/\d%/);
    expect(text).toContain("California drew new lines for 2026");
  });
});
