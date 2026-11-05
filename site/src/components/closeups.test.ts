import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";

import DistrictPage from "../pages/[state]/[district].astro";
import StatePage from "../pages/[state]/index.astro";
import { getDistrict, getState } from "../lib/data";
import MapCloseups from "./MapCloseups.astro";
import StateMapSvg from "./StateMapSvg.astro";

let container: AstroContainer;

beforeAll(async () => {
  container = await AstroContainer.create();
});

const figures = (html: string) => html.match(/<figure\b[\s\S]*?<\/figure>/g) ?? [];

describe("the state map", () => {
  it("outlines each close-up's area, but not the areas inside close-ups", async () => {
    const ca = await container.renderToString(StateMapSvg, { props: { state: "CA", stateName: "California" } });
    expect(ca.match(/<rect\b[^>]*class="closeup-box"/g)).toHaveLength(3);
    const wy = await container.renderToString(StateMapSvg, { props: { state: "WY", stateName: "Wyoming" } });
    expect(wy).not.toContain("closeup-box");
  });
});

describe("MapCloseups", () => {
  it("draws each close-up as a captioned, clickable map", async () => {
    const html = await container.renderToString(MapCloseups, { props: { state: "CA", stateName: "California" } });
    const panels = figures(html);
    expect(panels).toHaveLength(4);
    expect(panels[0]).toMatch(/<figcaption[^>]*>\s*Los Angeles area, enlarged 3 times\s*<\/figcaption>/);
    expect(panels[1]).toMatch(/<figcaption[^>]*>\s*Los Angeles area, closer in, enlarged 10 times\s*<\/figcaption>/);
    for (const panel of panels) {
      expect(panel).toMatch(/<svg\b[^>]*role="img"[^>]*aria-label="Close-up of the [^"]+ area(, closer in)?"/);
      const links = panel.match(/<a\b[^>]*>/g) ?? [];
      expect(links.length).toBeGreaterThan(1);
      // Out of the tab order, like the state map: the districts table has the same links.
      expect(links.filter((a) => !a.includes('tabindex="-1"'))).toEqual([]);
    }
  });

  it("marks cities in each close-up, with width rules of its own", async () => {
    const html = await container.renderToString(MapCloseups, { props: { state: "CA", stateName: "California" } });
    figures(html).forEach((panel, i) => {
      expect(panel).toMatch(new RegExp(`<g class="cities closeup-${i}-tier-0"`));
      expect(panel).toMatch(/<text\b[^>]*class="city-label"/);
    });
    expect(html).toContain("svg .cities.closeup-3-tier-0 { display: inline; }");
    expect(html).not.toContain("state-tier");
  });

  it("draws the close-ups that enlarge least across the whole width", async () => {
    const html = await container.renderToString(MapCloseups, { props: { state: "CA", stateName: "California" } });
    expect(figures(html).map((f) => /class="[^"]*\bwide\b/.test(f.slice(0, f.indexOf(">"))))).toEqual([
      true,
      true,
      true,
      false,
    ]);
  });

  it("outlines the area of a close-up of a close-up on its parent", async () => {
    const html = await container.renderToString(MapCloseups, { props: { state: "CA", stateName: "California" } });
    const boxes = figures(html).map((f) => (f.match(/<rect\b[^>]*class="closeup-box"/g) ?? []).length);
    expect(boxes).toEqual([1, 0, 0, 0]);
  });

  it("draws nothing for a state without close-ups", async () => {
    const html = await container.renderToString(MapCloseups, { props: { state: "WY", stateName: "Wyoming" } });
    expect(html.trim()).toBe("");
  });
});

describe("a state page with close-ups", () => {
  it("never repeats an element ID, though the map and its close-ups draw the same districts", async () => {
    const html = await container.renderToString(StatePage, { props: { state: getState("CA") } });
    const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
    expect(ids.length).toBeGreaterThan(100); // anchor: CA's map and its close-ups' shapes
    expect(ids.filter((id, i) => ids.indexOf(id) !== i)).toEqual([]);
    expect(figures(html)).toHaveLength(4);
  });
});

describe("a district page", () => {
  it("shows the closest close-up its district lies in, with the district outlined", async () => {
    const html = await container.renderToString(DistrictPage, { props: { district: getDistrict("CA-34") } });
    const [panel, ...rest] = figures(html);
    expect(rest).toEqual([]);
    expect(panel).toContain("Los Angeles area, closer in");
    expect(panel).toMatch(/class="outline current"/);
    // Its parent isn't shown, and neither are outlines for close-ups that aren't shown.
    expect(panel).not.toContain("closeup-box");
  });

  it("shows no close-up for a district big enough to see on the map", async () => {
    const html = await container.renderToString(DistrictPage, { props: { district: getDistrict("CA-01") } });
    expect(html).toMatch(/class="state-map\b/); // anchor: the map rendered
    expect(figures(html)).toEqual([]);
  });
});
