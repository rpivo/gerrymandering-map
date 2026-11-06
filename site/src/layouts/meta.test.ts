import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it } from "vitest";

import { SITE_URL } from "../lib/og";
import { getStaticPaths } from "../pages/og/[...image].png";
import Base from "./Base.astro";

/** Collect `<meta property|name="..." content="...">` tags as a map. */
function metaTags(html: string): Record<string, string> {
  const tags: Record<string, string> = {};
  for (const [, key = "", content = ""] of html.matchAll(/<meta (?:property|name)="([^"]+)" content="([^"]*)"/g)) {
    tags[key] = content;
  }
  return tags;
}

describe("link preview tags", () => {
  it("points social sites at the page's own image with absolute URLs", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, {
      props: { title: "TX-35", description: "About TX-35.", path: "/tx/35" },
    });
    expect(metaTags(html)).toMatchObject({
      "og:title": "TX-35",
      "og:description": "About TX-35.",
      "og:type": "website",
      "og:url": `${SITE_URL}/tx/35`,
      "og:image": `${SITE_URL}/og/tx/35.png`,
      "og:image:width": "1200",
      "og:image:height": "630",
      "twitter:card": "summary_large_image",
    });
    expect(metaTags(html)["og:image:alt"]).toBeTruthy();
  });

  it("uses gerrymandermap.us as the canonical address", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, {
      props: { title: "TX-35", description: "About TX-35.", path: "/tx/35" },
    });
    expect(html).toContain('<link rel="canonical" href="https://gerrymandermap.us/tx/35">');
    expect(metaTags(html)["og:image"]).toBe("https://gerrymandermap.us/og/tx/35.png");
  });

  it("uses the site-wide image for pages without their own, such as the 404 page", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, { props: { title: "Not found", description: "Missing." } });
    expect(metaTags(html)["og:image"]).toBe(`${SITE_URL}/og/index.png`);
    expect(metaTags(html)["og:url"]).toBeUndefined();
  });
});

describe("the site header", () => {
  it("keeps the theme switch out of the nav, so phones can put it beside the site name", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, { props: { title: "TX-35", description: "About TX-35." } });
    const header = html.slice(html.indexOf('<header class="site-header"'), html.indexOf("</header>"));
    const nav = header.slice(header.indexOf("<nav"), header.indexOf("</nav>"));
    expect(nav).toContain('href="/methodology"'); // anchor: the nav was found
    expect(nav).not.toContain("theme-toggle");
    expect(header).toContain('class="theme-toggle"');
  });
});

describe("preview image routes", () => {
  it("builds one image per district, per state, plus the home and methodology pages", () => {
    const images = getStaticPaths().map((p) => p.params.image);
    expect(images).toHaveLength(435 + 50 + 2);
    expect(new Set(images).size).toBe(images.length);
    expect(images).toEqual(expect.arrayContaining(["index", "methodology", "tx", "tx/35", "ak/al"]));
  });
});

describe("footer", () => {
  it("keeps a space on both sides of the separator between its links", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, { props: { title: "T", description: "D" } });
    const footer = html.slice(html.indexOf("<footer"), html.indexOf("</footer>"));
    const text = footer.replace(/<[^>]+>/g, "").replace(/\s+/g, " ");
    expect(text).toContain("How scores work · Source on GitHub");
  });

  it("invites people to buy a coffee on the Ko-fi page", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, { props: { title: "T", description: "D" } });
    const footer = html.slice(html.indexOf("<footer"), html.indexOf("</footer>"));
    const link = footer.match(/<a href="https:\/\/ko-fi\.com\/rpivovar"[^>]*>([\s\S]*?)<\/a>/)?.[1] ?? "";
    expect(link.replace(/<svg[\s\S]*?<\/svg>/, "").trim()).toBe("Buy me a coffee!");
    // A small coffee cup icon, decorative only, so screen readers read just the words.
    expect(link).toMatch(/^\s*<svg class="coffee"[^>]*aria-hidden="true"/);
    const text = footer.replace(/<[^>]+>/g, "").replace(/\s+/g, " ");
    expect(text).toContain("Source on GitHub · Like this project? Buy me a coffee!");
  });
});
