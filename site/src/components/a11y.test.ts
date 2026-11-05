import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";

import DistrictShape from "./DistrictShape.astro";
import FairnessSection from "./FairnessSection.astro";
import ScoreBadge from "./ScoreBadge.astro";
import PopulationNote from "./PopulationNote.astro";
import StateEdgeNote from "./StateEdgeNote.astro";
import StateMapSvg from "./StateMapSvg.astro";
import { getDistrict, getState } from "../lib/data";

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

describe("FairnessSection", () => {
  const render = async (usps: string) => {
    const html = await container.renderToString(FairnessSection, { props: { state: getState(usps) } });
    return { html, text: html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim() };
  };

  it("shows each measure's number with the direction it leans in words", async () => {
    const { html, text } = await render("NC");
    expect(html).toContain('aria-labelledby="fairness-heading"');
    expect(text).toContain("Efficiency gap 25.7% Favors Republicans");
    expect(text).toContain("Mean-median difference 5.8 points Favors Republicans");
    expect(text).toContain("Declination 0.58 Favors Republicans");
    expect(text).toContain("carried 3 of 14 districts");
    expect(text).toContain("official 2024 results");
    expect(html).toContain('href="/methodology#fairness"');
  });

  it("keeps a space between the number and its direction, as screen readers read them", async () => {
    const { html } = await render("NC");
    // Screen readers join inline text without spaces, so strip tags without adding any.
    const joined = html.replace(/<[^>]+>/g, "").replace(/\s+/g, " ");
    expect(joined).toContain("25.7% Favors Republicans");
  });

  it("names a state that favors Democrats that way", async () => {
    const { text } = await render("IL");
    expect(text).toMatch(/Efficiency gap \d+\.\d% Favors Democrats/);
  });

  it("explains a sweep, and doesn't show a declination", async () => {
    const { text } = await render("CT");
    expect(text).toContain("carried all 5 districts");
    expect(text).toContain("Declination Not measurable");
    expect(text).toMatch(/When one party carries every district, the efficiency gap/);
  });

  it("leaves the sweep note off a state that split its districts", async () => {
    const { text } = await render("NC");
    expect(text).toContain("Declination 0.58"); // anchor: this is the scored layout
    expect(text).not.toContain("When one party carries every district");
  });

  it("says why an unscored state has no scores, and shows none", async () => {
    const { text } = await render("UT");
    expect(text).toContain("2026 House results");
    expect(text).not.toContain("Efficiency gap");
  });

  it("never calls a map gerrymandered", async () => {
    for (const usps of ["NC", "IL", "CT", "UT", "WY", "NH"]) {
      const { text } = await render(usps);
      expect(text.length).toBeGreaterThan(50); // anchor: there is text to check
      expect(text.toLowerCase()).not.toContain("gerrymander");
    }
  });
});

describe("StateEdgeNote", () => {
  const render = async (id: string) => {
    const html = await container.renderToString(StateEdgeNote, { props: { district: getDistrict(id) } });
    const text = html.replace(/<[^>]+>/g, " ").replace(/&#39;/g, "'").replace(/\s+/g, " ").trim();
    return { html, text };
  };

  it("gives the share and says what it means for the scores", async () => {
    const { html, text } = await render("TX-23");
    expect(html).toContain('aria-labelledby="edge-heading"');
    expect(text).toContain("53% of this district's border is the state's edge");
    expect(text).toContain("Polsby-Popper");
    expect(html).toContain('href="/methodology#state-edge"');
  });

  it("is left off a district drawn entirely by mapmakers", async () => {
    expect((await render("CO-01")).text).toBe("");
  });

  it("is left off at-large districts, whose shape is the state's shape", async () => {
    expect((await render("WY-AL")).text).toBe("");
  });
});

describe("PopulationNote", () => {
  const render = async (id: string) => {
    const html = await container.renderToString(PopulationNote, { props: { id } });
    const text = html.replace(/<[^>]+>/g, " ").replace(/&#39;/g, "'").replace(/\s+/g, " ").trim();
    return { html, text };
  };

  it("names the majority and gives the Voting Rights Act context without claiming intent", async () => {
    const { html, text } = await render("AL-07");
    expect(html).toContain('aria-labelledby="population-heading"');
    expect(text).toContain("Most of this district's voting-age residents are Black (50.4%).");
    expect(text).toContain("Voting Rights Act");
    expect(text).toContain("doesn't know whether this one was");
    expect(text).toContain("2020 Census");
    expect(html).toContain('href="/methodology#population"');
    expect(text.toLowerCase()).not.toContain("gerrymander");
  });

  it("describes a coalition district", async () => {
    const { text } = await render("NJ-08");
    expect(text).toMatch(/\(\d+\.\d%\) belong to minority groups\. The largest/);
  });

  it("is left off a district without a minority majority", async () => {
    expect((await render("WY-AL")).text).toBe("");
  });
});
