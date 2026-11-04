import { describe, expect, it } from "vitest";

import headersFile from "../../public/_headers?raw";

/** Parse a Cloudflare Pages _headers file into { path: { header: value } }. */
function parseHeaders(text: string): Record<string, Record<string, string>> {
  const rules: Record<string, Record<string, string>> = {};
  let current: Record<string, string> | null = null;
  for (const line of text.split("\n")) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    if (!line.startsWith(" ")) {
      current = rules[line.trim()] = {};
    } else if (current) {
      const [name, ...value] = line.trim().split(":");
      current[name?.trim().toLowerCase() ?? ""] = value.join(":").trim();
    }
  }
  return rules;
}

const rules = parseHeaders(headersFile);

describe("Cloudflare Pages headers", () => {
  it("sends security headers on every page", () => {
    expect(rules["/*"]).toMatchObject({
      "x-content-type-options": "nosniff",
      "referrer-policy": "strict-origin-when-cross-origin",
      "x-frame-options": "DENY",
    });
  });

  it("caches fingerprinted build assets for a year", () => {
    expect(rules["/_astro/*"]?.["cache-control"]).toBe("public, max-age=31536000, immutable");
  });

  it("doesn't cache pages forever", () => {
    expect(rules["/*"]?.["cache-control"]).toBeUndefined();
  });
});
