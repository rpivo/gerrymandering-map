import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it } from "vitest";

import DistrictPage from "../pages/[state]/[district].astro";
import StatePage from "../pages/[state]/index.astro";
import { getDistrict, states } from "./data";
import { asOfDate, getSenators } from "./senators";

/** The senators section's text, from its heading to its end. */
function section(html: string): string {
  const start = html.indexOf('id="senators-heading"');
  expect(start).toBeGreaterThan(-1); // anchor: the section rendered
  return html
    .slice(start, html.indexOf("</section>", start))
    .replace(/<[^>]+>/g, " ")
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ");
}

describe("senators data", () => {
  it("has two senators for every state", () => {
    expect(states).toHaveLength(50); // anchor: the loop checks something
    for (const s of states) {
      expect(getSenators(s.state), s.state).toHaveLength(2);
    }
  });

  it("formats the date the list was taken as words", () => {
    expect(asOfDate("2026-11-06")).toBe("November 6, 2026");
  });
});

describe("a district page's senators", () => {
  const render = async (id: string) => {
    const container = await AstroContainer.create();
    return container.renderToString(DistrictPage, { props: { district: getDistrict(id) } });
  };

  it("names the state's two senators and their parties in words, after the vote", async () => {
    const html = await render("ME-02");
    const start = html.indexOf('id="senators-heading"');
    expect(start).toBeGreaterThan(html.indexOf('id="president-heading"'));
    expect(start).toBeLessThan(html.indexOf('id="state-heading"'));
    const text = section(html);
    expect(text).toContain("Maine's senators");
    expect(text).toContain("Susan M. Collins, Republican");
    expect(text).toContain("Angus S. King Jr., Independent");
  });

  it("says senators represent the whole state, when the list is from, and that it changes in January", async () => {
    const text = section(await render("TX-35"));
    expect(text).toContain("Senators are elected by the whole state, so district lines don't change who they are.");
    expect(text).toContain("As of November 6, 2026");
    expect(text).toContain("take office January 3, 2027");
    expect(section(await render("TX-35"))).toBe(text); // stable across renders
  });

  it("links to the methodology page for the source", async () => {
    const html = await render("TX-35");
    const start = html.indexOf('id="senators-heading"');
    expect(html.slice(start, html.indexOf("</section>", start))).toContain('href="/methodology#senators"');
  });
});

describe("a state page's senators", () => {
  it("names the state's senators before the fairness section", async () => {
    const container = await AstroContainer.create();
    const state = states.find((s) => s.state === "VT");
    const html = await container.renderToString(StatePage, { props: { state } });
    const start = html.indexOf('id="senators-heading"');
    expect(start).toBeGreaterThan(html.indexOf('id="table-heading"'));
    expect(start).toBeLessThan(html.indexOf('id="fairness-heading"'));
    expect(section(html)).toContain("Bernard Sanders, Independent");
  });
});
