import css from "../styles/global.css?raw";

/**
 * Read the #rrggbb custom properties in the first `:root { ... }` block at or after `start`.
 * @param start - Where in global.css to start looking.
 * @returns Token name (without the leading --) to color.
 */
function readRoot(start: number): Record<string, string> {
  const open = css.indexOf(":root {", start);
  if (open < 0) {
    throw new Error("global.css has no :root block where expected.");
  }
  const body = css.slice(open, css.indexOf("}", open));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
}

/**
 * Read the light theme's color tokens from global.css, so images drawn at build time match the site.
 * @returns Token name (without the leading --) to a #rrggbb color.
 */
export function lightTokens(): Record<string, string> {
  return readRoot(0);
}

/**
 * Read the dark theme's color tokens: the light ones with the dark overrides applied.
 * @returns Token name (without the leading --) to a #rrggbb color.
 */
export function darkTokens(): Record<string, string> {
  return { ...readRoot(0), ...readRoot(css.indexOf("prefers-color-scheme: dark")) };
}
