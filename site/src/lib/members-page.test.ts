import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it } from "vitest";

import DistrictPage from "../pages/[state]/[district].astro";
import { getDistrict } from "./data";

async function sectionText(id: string, heading: string): Promise<{ html: string; text: string }> {
  const container = await AstroContainer.create();
  const page = await container.renderToString(DistrictPage, { props: { district: getDistrict(id) } });
  const start = page.indexOf(`id="${heading}"`);
  expect(start).toBeGreaterThan(-1); // anchor: the section rendered
  const html = page.slice(start, page.indexOf("</section>", start));
  return { html, text: html.replace(/<[^>]+>/g, " ").replace(/&#39;/g, "'").replace(/\s+/g, " ") };
}

describe("a district page's House race", () => {
  it("names the winner of a called race, with the state's results page", async () => {
    const { html, text } = await sectionText("TX-35", "house-heading");
    expect(text).toContain("Johnny C. Garcia, Democrat");
    expect(text).toContain("Elected November 3, 2026, takes office January 3, 2027.");
    expect(text).toContain("Unofficial results from the Texas Secretary of State");
    expect(html).toContain('href="/methodology#members"');
  });

  it("names nobody in an uncalled race", async () => {
    const { text } = await sectionText("AZ-02", "house-heading");
    expect(text).toContain("hasn't been called yet");
    expect(text).not.toMatch(/Democrat|Republican/);
  });

  it("gives the runoff date and names nobody", async () => {
    const { text } = await sectionText("LA-05", "house-heading");
    expect(text).toContain("goes to a runoff on December 12, 2026");
    expect(text).not.toMatch(/Democrat|Republican/);
  });

  it("says when the state's results aren't available, without a results link", async () => {
    const { text } = await sectionText("MI-04", "house-heading");
    expect(text).toContain("Statewide results from Michigan for the November 3, 2026 election aren't available yet.");
    expect(text).not.toContain("Unofficial results from");
  });

  it("comes after the 2024 vote and before the senators", async () => {
    const container = await AstroContainer.create();
    const page = await container.renderToString(DistrictPage, { props: { district: getDistrict("TX-35") } });
    const house = page.indexOf('id="house-heading"');
    expect(house).toBeGreaterThan(page.indexOf('id="president-heading"'));
    expect(house).toBeLessThan(page.indexOf('id="senators-heading"'));
  });
});

describe("a district page's senators and the 2026 ballot", () => {
  it("says a senator was re-elected", async () => {
    const { text } = await sectionText("GA-05", "senators-heading");
    expect(text).toMatch(/Ossoff, Democrat Re-elected November 3, 2026\./);
  });

  it("names who won a seat from the senator holding it, only on that seat", async () => {
    const { text } = await sectionText("OH-03", "senators-heading");
    expect(text).toContain(
      "Jon Husted, Republican Seat on the November 3, 2026 ballot: Sherrod Brown, Democrat, won and takes office January 3, 2027.",
    );
    expect(text).toMatch(/Bernie Moreno, Republican (?!Seat)/); // class 1: not on the ballot
  });

  it("says when a seat's results aren't available", async () => {
    const { text } = await sectionText("ME-01", "senators-heading");
    expect(text).toContain("Susan M. Collins, Republican Seat on the November 3, 2026 ballot: results aren't available yet.");
  });
});
