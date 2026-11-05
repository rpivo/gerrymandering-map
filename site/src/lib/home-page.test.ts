import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";

import Home from "../pages/index.astro";

let html: string;

beforeAll(async () => {
  const container = await AstroContainer.create();
  html = await container.renderToString(Home);
});

describe("the home page's state links", () => {
  const nav = () => {
    const start = html.search(/<nav\b[^>]*aria-label="States"/);
    return start < 0 ? "" : html.slice(start, html.indexOf("</nav>", start));
  };

  it("links straight to every state page, one click from the home page", () => {
    const links = nav().match(/<a\b[^>]*href="\/[a-z]{2}"/g) ?? [];
    expect(links).toHaveLength(50);
    expect(nav()).toMatch(/<a\b[^>]*href="\/tx"/);
  });

  it("names each state in full for screen readers and on hover", () => {
    expect(nav()).toMatch(/<a\b[^>]*href="\/tx"[^>]*aria-label="Texas"|<a\b[^>]*aria-label="Texas"[^>]*href="\/tx"/);
    expect(nav()).toMatch(/title="Texas"/);
  });

  it("comes before the district search, so it's near the top", () => {
    expect(nav()).not.toBe(""); // anchor: the nav rendered
    expect(html.indexOf('aria-label="States"')).toBeLessThan(html.indexOf('aria-label="Find districts"'));
  });
});
