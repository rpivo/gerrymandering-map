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

  it("credits every vote data source", () => {
    const votes = sources.filter((s) => s.role === "votes");
    expect(votes).toHaveLength(6); // anchor: the loop checks something
    for (const s of votes) {
      expect(html).toContain(`href="${s.url}"`);
    }
  });
});
