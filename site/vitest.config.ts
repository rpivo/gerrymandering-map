/// <reference types="vitest/config" />
// Use Astro's Vite setup so tests can render .astro components with the container API.
import { getViteConfig } from "astro/config";

// css: true, or Vitest hands `?raw` CSS imports to tests as an empty string.
export default getViteConfig({ test: { css: true } });
