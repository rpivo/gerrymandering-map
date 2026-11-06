import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";

import Home from "../pages/index.astro";

let html: string;

beforeAll(async () => {
  const container = await AstroContainer.create();
  html = await container.renderToString(Home);
});

const nav = () => {
  const start = html.search(/<nav\b[^>]*aria-label="States"/);
  return start < 0 ? "" : html.slice(start, html.indexOf("</nav>", start));
};

// The links a keyboard or screen reader reaches: everything not taken out of the tab order.
const stateLinks = () => (nav().match(/<a\b[^>]*>/g) ?? []).filter((a) => !a.includes('tabindex="-1"'));

describe("the home page's US map", () => {
  it("links straight to every state page from its shape, one click from the home page", () => {
    const shapes = nav().match(/<a\b[^>]*href="\/[a-z]{2}"[^>]*>\s*<title>[^<]+<\/title>\s*<path\b/g) ?? [];
    expect(shapes).toHaveLength(50);
    expect(stateLinks()).toHaveLength(50);
  });

  it("names each state in full for screen readers and on hover", () => {
    expect(nav()).toMatch(/<a\b[^>]*href="\/tx"[^>]*aria-label="Texas"|<a\b[^>]*aria-label="Texas"[^>]*href="\/tx"/);
    expect(nav()).toContain("<title>Texas</title>");
  });

  it("labels the states that are big enough, on the map", () => {
    expect(nav()).toMatch(/<text\b[^>]*>TX<\/text>/);
  });

  it("gives the small northeastern states labeled boxes beside the map, outside the tab order", () => {
    for (const state of ["vt", "nh", "ma", "ri", "ct", "nj", "de", "md"]) {
      const boxes = nav().match(new RegExp(`<a\\b[^>]*href="/${state}"[^>]*class="callout"[^>]*>`, "g")) ?? [];
      expect(boxes, state).toHaveLength(1);
      expect(boxes[0]).toContain('tabindex="-1"');
    }
  });

  it("also lists the small states as buttons big enough to tap, north to south, outside the tab order", () => {
    const list = nav().match(/<ul\b[^>]*class="small-states"[\s\S]*?<\/ul>/)?.[0] ?? "";
    const links = list.match(/<a\b[^>]*>/g) ?? [];
    const hrefs = links.map((a) => a.match(/href="\/([a-z]{2})"/)?.[1]);
    expect(hrefs).toEqual(["vt", "nh", "ma", "ri", "ct", "nj", "md", "de"]);
    expect(links.every((a) => a.includes('tabindex="-1"'))).toBe(true);
  });

  it("lets a state's label be tapped too, not only its shape", () => {
    const source = Object.values(
      import.meta.glob<string>("../components/UsMap.astro", { query: "?raw", import: "default", eager: true }),
    )[0];
    expect(source).toMatch(/<style>[\s\S]*text \{/); // anchor: the label styles were read
    expect(source).not.toMatch(/pointer-events:\s*none/);
  });

  it("comes before the district search, so it's near the top", () => {
    expect(nav()).not.toBe(""); // anchor: the nav rendered
    expect(html.indexOf('aria-label="States"')).toBeLessThan(html.indexOf('aria-label="Find districts"'));
  });
});

describe("the home page's introduction", () => {
  const paragraph = (cls: string) => {
    const start = html.indexOf(`<p class="${cls}"`);
    expect(start).toBeGreaterThan(-1); // anchor: the paragraph rendered
    return html.slice(start, html.indexOf("</p>", start));
  };

  it("links to how scores work from the note about shape, not from the opening line", () => {
    expect(paragraph("note")).toContain("A score describes shape, not intent.");
    expect(paragraph("note")).toMatch(/<a href="\/methodology"[^>]*>How scores work<\/a>/);
    expect(paragraph("lede")).not.toContain('href="/methodology"');
  });
});

describe("the home page's ZIP code search", () => {
  it("says a ZIP code works, and has a line that announces what a ZIP code search found", () => {
    expect(html).toMatch(/<input[^>]*name="query"[^>]*placeholder="TX-35, Texas or a ZIP code"/);
    expect(html).toMatch(/<p[^>]*class="zip-message"[^>]*aria-live="polite"[^>]*data-zip-message[^>]*hidden/);
  });
});
