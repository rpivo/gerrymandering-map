import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";

import Methodology from "../pages/methodology.astro";
import { sources } from "./data";

let text: string;
let html: string;

beforeAll(async () => {
  const container = await AstroContainer.create();
  html = await container.renderToString(Methodology);
  text = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
});

describe("the methodology page", () => {
  it("explains how a district's cities and towns are counted", () => {
    expect(html).toMatch(/<h2[^>]*id="places"/);
    expect(text).toContain("census-designated places");
    expect(text).toContain("all of its 2020 residents");
  });

  it("says which cities the state maps mark, and where the points come from", () => {
    expect(text).toContain("State maps mark the largest places");
    expect(text).toContain("at the census block nearest where the place's residents live on average");
    expect(text).not.toContain("internal point");
  });

  it("says how district outlines place a dot for a split city", () => {
    expect(text).toContain("Each district page's outline marks the district's own largest places");
    expect(text).toContain("gets a dot in each part");
  });

  it("explains when a state map gets close-ups, and that they're for display only", () => {
    expect(html).toMatch(/<h2[^>]*id="closeups"/);
    expect(text).toContain("less than 8 pixels from its middle to its edge");
    expect(text).toContain("redrawn from the detailed district lines");
    expect(text).toContain("a close-up of its own");
    expect(text).toContain("Scores always use each district's full shape");
    expect(text).toContain("Close-ups mark the largest places in them the same way as state maps");
  });

  it("has a fairness section the state pages can link to", () => {
    expect(html).toMatch(/<h2[^>]*id="fairness"/);
  });

  it("explains each fairness measure and the sign convention", () => {
    for (const name of ["Efficiency gap", "Mean-median difference", "Declination"]) {
      expect(text).toContain(name);
    }
    expect(text).toContain("4 or more districts");
  });

  it("explains the state's edge share the district pages link to", () => {
    expect(html).toMatch(/<h2[^>]*id="state-edge"/);
    expect(text).toContain("100 meters");
  });

  it("explains how population is counted, for the district pages' note", () => {
    expect(html).toMatch(/<h2[^>]*id="population"/);
    expect(text).toContain("alone or in combination");
    expect(text).toContain("prison");
  });

  it("credits the Census redistricting files once, not 50 times", () => {
    expect(sources.filter((s) => s.role === "population")).toHaveLength(50); // anchor
    expect(text.match(/Redistricting Data \(PL 94-171\)/g)).toHaveLength(1);
    expect(html).toContain('href="https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/"');
  });

  it("credits every vote data source", () => {
    const votes = sources.filter((s) => s.role === "votes");
    expect(votes).toHaveLength(6); // anchor: the loop checks something
    for (const s of votes) {
      expect(html).toContain(`href="${s.url}"`);
    }
  });
});
