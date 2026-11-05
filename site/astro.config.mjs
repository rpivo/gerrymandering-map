// @ts-check
import { defineConfig } from "astro/config";

// Fully static output: every page is pre-rendered at build time.
export default defineConfig({
  output: "static",
  // Build tx/35.html rather than tx/35/index.html, so Cloudflare serves /tx/35 directly
  // instead of redirecting it to /tx/35/. Every link on the site omits the slash.
  build: { format: "file" },
  trailingSlash: "never",
  // 4321 to 4323 are used by other local sites.
  server: { port: 4324 },
  // Keep the dev toolbar out of preview screenshots.
  devToolbar: { enabled: false },
});
