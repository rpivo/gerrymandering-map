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

describe("StateMapSvg hover outline", () => {
  // SVG has no z-index: later shapes paint over earlier ones. If each link drew its own fill,
  // a hovered district's outline would be partly covered by neighbors drawn after it.
  it("draws every district's fill before the first link, so a hover outline is never covered", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "TX", stateName: "Texas" } });
    const fills = [...html.matchAll(/<use\b[^>]*class="[^"]*\bfill\b/g)].map((m) => m.index);
    // Anchor: one fill per Texas district, so an empty match can't pass vacuously.
    expect(fills).toHaveLength(38);
    expect(Math.max(...fills)).toBeLessThan(html.indexOf("<a "));
  });

  it("gives each district one shape, shared by its fill and its link", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "TX", stateName: "Texas" } });
    expect(html.match(/<path\b/g)).toHaveLength(38);
    expect(html.match(/<use\b/g)).toHaveLength(76);
  });

  it("keeps every district's score color on a district page", async () => {
    const html = await container.renderToString(StateMapSvg, {
      props: { state: "TX", stateName: "Texas", highlight: "TX-25" },
    });
    const fills = html.match(/<use\b[^>]*class="fill band-[a-z-]+[^"]*"/g) ?? [];
    // Anchor: every Texas district is scored, so all 38 fills carry a band.
    expect(fills).toHaveLength(38);
    // has-highlight is what used to turn every other district gray.
    expect(html).not.toContain("has-highlight");
  });

  it("outlines the highlighted district in the top layer, so it stands out among the colors", async () => {
    const html = await container.renderToString(StateMapSvg, {
      props: { state: "TX", stateName: "Texas", highlight: "TX-25" },
    });
    const start = html.search(/<a\b[^>]*data-tip="TX-25"/);
    const link = html.slice(start, html.indexOf("</a>", start));
    expect(start).toBeGreaterThan(-1);
    expect(link).toMatch(/<use\b[^>]*class="outline current"/);
    expect(html.match(/class="outline current"/g)).toHaveLength(1);
    // A halo in the page color goes under the outline, so the outline shows on any band.
    expect(link).toMatch(/<use\b[^>]*class="halo"[^>]*>(?:<\/use>)?\s*<use\b[^>]*class="outline current"/);
    expect(html.match(/class="halo"/g)).toHaveLength(1);
  });
});

describe("StateMapSvg city marks", () => {
  async function tennessee(): Promise<string> {
    return container.renderToString(StateMapSvg, { props: { state: "TN", stateName: "Tennessee" } });
  }

  it("draws city marks on top of the districts, without taking hovers or clicks from them", async () => {
    const html = await tennessee();
    const groups = [...html.matchAll(/<g\b[^>]*class="cities tier-\d[^"]*"[^>]*>/g)];
    // Anchor: Tennessee's wide map is drawn at every width tier.
    expect(groups.length).toBeGreaterThanOrEqual(4);
    const lastLink = html.lastIndexOf("</a>");
    expect(groups.every((g) => g.index > lastLink)).toBe(true);
    expect(groups.every(([g]) => g.includes('pointer-events="none"'))).toBe(true);
    // The map is one labeled image; the marks add nothing a screen reader should read twice.
    expect(groups.every(([g]) => g.includes('aria-hidden="true"'))).toBe(true);
  });

  it("labels the state's big cities with a dot each", async () => {
    const html = await tennessee();
    const widest = html.slice(html.lastIndexOf('class="cities tier-'));
    const labels = [...widest.matchAll(/<text\b[^>]*>([^<]+)<\/text>/g)].map((m) => m[1]);
    expect(labels).toEqual(expect.arrayContaining(["Nashville", "Memphis", "Knoxville", "Chattanooga"]));
    expect(widest.match(/<circle\b/g)?.length).toBe(labels.length);
  });

  it("shows one tier at a time, picked by how wide the map is drawn", async () => {
    const html = await tennessee();
    expect(html).toMatch(/class="map-frame"[^>]*style="[^"]*container-type: inline-size/);
    expect(html).toMatch(/@container \(max-width: 399\.98px\) \{ \.map-frame \.tier-0 \{ display: inline; \} \}/);
    expect(html).toMatch(
      /@container \(min-width: 400px\) and \(max-width: 519\.98px\) \{ \.map-frame \.tier-1 \{ display: inline; \} \}/,
    );
  });
});

describe("StateMapSvg city marks on a map drawn at one size", () => {
  it("always shows the one set of marks, with no container query to fail", async () => {
    // New Jersey's map is never drawn wider than about 269px, so it has a single tier.
    const html = await container.renderToString(StateMapSvg, { props: { state: "NJ", stateName: "New Jersey" } });
    expect(html.match(/class="cities tier-\d/g)).toEqual(['class="cities tier-0']);
    expect(html).toContain(".map-frame .tier-0 { display: inline; }");
    expect(html).not.toMatch(/@container\s*\{/);
  });
});

describe("StateMapSvg tooltips", () => {
  it("has one hidden tooltip per district, out of the accessibility tree", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "TX", stateName: "Texas" } });
    const tips = html.match(/<div\b[^>]*class="map-tip[^"]*"[^>]*>/g) ?? [];
    // Anchor: one per Texas district, so an empty match can't pass vacuously.
    expect(tips).toHaveLength(38);
    expect(tips.filter((t) => !t.includes('aria-hidden="true"'))).toEqual([]);
  });

  it("shows a district's tooltip only while that district is hovered", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "TX", stateName: "Texas" } });
    // The selector list must end in the rule that shows the tooltip, or it does nothing.
    expect(html).toMatch(
      /\.map-frame:has\(a\[data-tip="TX-25"\]:hover\) \.map-tip\[data-tip="TX-25"\][^{]*\{ display: block; \}/,
    );
    expect(html).toMatch(/<a\b[^>]*data-tip="TX-25"/);
    expect(html).toMatch(/class="map-tip[^"]*"[^>]*data-tip="TX-25"|data-tip="TX-25"[^>]*class="map-tip/);
  });

  it("tells the district's score and context in the tooltip", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "TX", stateName: "Texas" } });
    const start = html.search(/<div\b[^>]*data-tip="TX-25"/);
    const tip = html.slice(start, html.indexOf("</div>", start));
    expect(start).toBeGreaterThan(-1);
    expect(tip).toContain("TX-25");
    expect(tip).toMatch(/Irregularity score \d+/);
    expect(tip).toContain("least compact of 38 in Texas");
  });

  it("drops the browser's own title tooltip, which would show on top of the new one", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "TX", stateName: "Texas" } });
    expect(html).toContain("<svg"); // anchor: the map rendered
    expect(html).not.toContain("<title>");
  });
});

describe("StateMapSvg notes", () => {
  it("says what a cropped map leaves out", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "HI", stateName: "Hawaii" } });
    expect(html).toContain("The Northwestern Hawaiian Islands, part of District 2, are not shown.");
  });

  it("has no note for a map drawn in full", async () => {
    const html = await container.renderToString(StateMapSvg, { props: { state: "TX", stateName: "Texas" } });
    expect(html).toContain("<svg"); // anchor: the map rendered
    expect(html).not.toContain("not shown");
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
