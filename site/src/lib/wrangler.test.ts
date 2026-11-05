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

  it("has a previews block, which `wrangler preview` requires, so it can be tried again for PR builds", () => {
    expect(config).toHaveProperty("previews");
  });

  it("sets a compatibility date", () => {
    expect(config.compatibility_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
