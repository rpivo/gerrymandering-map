import { describe, expect, it } from "vitest";

import config from "../../wrangler.json";

describe("Cloudflare Worker config", () => {
  it("serves the Astro build as static assets", () => {
    expect(config.name).toBe("gerrymandering-map");
    expect(config.assets.directory).toBe("./dist");
  });

  it("has no Worker script: the site is static files only", () => {
    expect("main" in config).toBe(false);
  });

  it("serves the site on gerrymandermap.us, with www attached for its redirect", () => {
    expect(config.routes).toEqual([
      { pattern: "gerrymandermap.us", custom_domain: true },
      { pattern: "www.gerrymandermap.us", custom_domain: true },
    ]);
  });

  it("keeps the workers.dev address on: wrangler turns it off when routes are set", () => {
    expect(config.workers_dev).toBe(true);
  });

  it("sets a compatibility date", () => {
    expect(config.compatibility_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
