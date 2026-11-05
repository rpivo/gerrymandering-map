import { describe, expect, it } from "vitest";

import config from "../../astro.config.mjs";

describe("page URLs", () => {
  it("builds pages as files (tx/35.html) so /tx/35 is served without a redirect", () => {
    expect(config.build?.format).toBe("file");
  });

  it("links never end in a slash", () => {
    expect(config.trailingSlash).toBe("never");
  });

  it("has a not-found page for Cloudflare's 404-page handling", () => {
    expect(Object.keys(import.meta.glob("../pages/404.astro"))).toHaveLength(1);
  });
});
