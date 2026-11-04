// @ts-check
import { defineConfig } from "astro/config";

// Fully static output: every page is pre-rendered at build time.
export default defineConfig({
  output: "static",
  // 4321 to 4323 are used by other local sites.
  server: { port: 4324 },
  // Keep the dev toolbar out of preview screenshots.
  devToolbar: { enabled: false },
});
