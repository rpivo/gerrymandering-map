import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it } from "vitest";

import Base from "../layouts/Base.astro";
import Home from "../pages/index.astro";
import { districtCardSvg } from "./og";

// Every source file under site/src as text, skipping tests and generated data.
const sources = Object.entries(
  import.meta.glob<string>("../**/*.{astro,ts}", { query: "?raw", import: "default", eager: true }),
).filter(([path]) => !path.endsWith(".test.ts") && !path.startsWith("../data/"));

describe("the site's name", () => {
  it("is Gerrymander Map in the header, with the domain beneath it", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, { props: { title: "TX-35", description: "About TX-35." } });
    const header = html.slice(html.indexOf('<header class="site-header"'), html.indexOf("</header>"));
    expect(header).toMatch(/class="site-name"[^>]*>\s*Gerrymander Map\s*</);
    expect(header).toMatch(/class="site-domain"[^>]*>\s*gerrymandermap\.us\s*</);
    expect(html).toContain('<meta property="og:site_name" content="Gerrymander Map">');
  });

  it("is the home page's heading and title", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Home);
    expect(html).toMatch(/<h1[^>]*>Gerrymander Map<\/h1>/);
    expect(html).toContain("<title>Gerrymander Map</title>");
  });

  it("is on the link preview images", () => {
    expect(districtCardSvg("TX-35")).toContain(">GERRYMANDER MAP<");
  });

  it("no longer appears as Gerrymandering Map anywhere in the site's code", () => {
    expect(sources.length).toBeGreaterThan(20); // anchor: the sweep read real files
    const old = sources.filter(([, text]) => /gerrymandering map/i.test(text)).map(([path]) => path);
    expect(old).toEqual([]);
  });
});
