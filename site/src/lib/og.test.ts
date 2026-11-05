import { describe, expect, it } from "vitest";

import { getDistrict, outline, stateMap } from "./data";
import { scoreBand } from "./format";
import { districtCardSvg, escapeXml, ogImagePath, siteCardSvg, stateCardSvg, wrapText } from "./og";
import { lightTokens } from "./tokens";

describe("ogImagePath", () => {
  it.each([
    ["/", "/og/index.png"],
    ["/methodology", "/og/methodology.png"],
    ["/tx", "/og/tx.png"],
    ["/tx/35", "/og/tx/35.png"],
  ])("maps %s to %s", (page, image) => {
    expect(ogImagePath(page)).toBe(image);
  });
});

describe("wrapText", () => {
  it("breaks between words to fit the line length", () => {
    expect(wrapText("South Dakota At-Large District", 18)).toEqual(["South Dakota", "At-Large District"]);
  });

  it("keeps short text on one line", () => {
    expect(wrapText("Texas District 35", 18)).toEqual(["Texas District 35"]);
  });

  it("never splits a word, even one longer than the line", () => {
    expect(wrapText("Massachusetts", 5)).toEqual(["Massachusetts"]);
  });
});

describe("escapeXml", () => {
  it("escapes the characters SVG text can't hold", () => {
    expect(escapeXml(`A & <B> "C" 'D'`)).toBe("A &amp; &lt;B&gt; &quot;C&quot; &apos;D&apos;");
  });
});

/** The text an SVG would display, with tags removed and entities left as they are. */
function svgText(svg: string): string {
  return svg.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
}

describe("districtCardSvg", () => {
  const district = getDistrict("TX-35");
  const svg = districtCardSvg("TX-35");

  it("is a 1200 by 630 image, the size link previews expect", () => {
    expect(svg).toMatch(/^<svg [^>]*width="1200" height="630"/);
  });

  it("shows the ID, name, score, band and comparison", () => {
    const text = svgText(svg);
    expect(text).toContain("TX-35");
    expect(text).toContain("Texas District 35");
    expect(text).toContain(`Irregularity score ${district.irregularity}`);
    expect(text).toMatch(/Less compact than \d+% of other districts/);
    expect(text).toContain("Scores describe shape, not intent.");
  });

  it("draws the district's detailed outline", () => {
    expect(svg).toContain(`d="${outline("TX-35", "page").d}"`);
  });

  it("fills the score pill with the district's band color from the site's light theme", () => {
    const band = scoreBand(district.irregularity ?? -1).key;
    expect(svg).toContain(`fill="${lightTokens()[`band-${band}`]}"`);
  });

  it("says an at-large district isn't ranked, without a comparison", () => {
    const text = svgText(districtCardSvg("AK-AL"));
    expect(text).toContain("Alaska At-Large District");
    expect(text).toContain("Not ranked");
    expect(text).not.toContain("Less compact");
  });
});

describe("stateCardSvg", () => {
  it("draws every district on the state map, with the name and count", () => {
    const svg = stateCardSvg("TX");
    const paths = Object.keys(stateMap("TX").paths);
    // Anchor: Texas has 38 districts, so an empty map can't pass.
    expect(paths).toHaveLength(38);
    expect(svg.match(/<path /g)).toHaveLength(38);
    expect(svgText(svg)).toContain("Texas");
    expect(svgText(svg)).toContain("38 congressional districts");
  });
});

describe("siteCardSvg", () => {
  it("shows the given title and subtitle, escaped", () => {
    const text = svgText(siteCardSvg("How scores work", "Shape & intent"));
    expect(text).toContain("How scores work");
    expect(text).toContain("Shape &amp; intent");
  });
});
