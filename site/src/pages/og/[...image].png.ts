import type { APIRoute } from "astro";

import { districts, states } from "../../lib/data";
import { districtPath } from "../../lib/districts";
import { districtCardSvg, siteCardSvg, stateCardSvg } from "../../lib/og";
import { assertFontsLoad, renderPng } from "../../lib/og-render";

const SITE_CARDS: Record<string, [string, string]> = {
  index: ["Gerrymander Map", "How irregular is the shape of every US congressional district?"],
  methodology: ["How scores work", "Three compactness measures, and what they can't tell you."],
};

/**
 * Map each image path (`tx/35`) to a function that draws its card.
 * @returns Image path to card drawer.
 */
function cards(): Map<string, () => string> {
  const map = new Map<string, () => string>();
  for (const [key, [title, subtitle]] of Object.entries(SITE_CARDS)) {
    map.set(key, () => siteCardSvg(title, subtitle));
  }
  for (const s of states) {
    map.set(s.state.toLowerCase(), () => stateCardSvg(s.state));
  }
  for (const d of districts) {
    map.set(districtPath(d.id).slice(1), () => districtCardSvg(d.id));
  }
  return map;
}

/**
 * List every preview image to build: the home and methodology pages, each state and each district.
 * @returns One route per image, such as `{ params: { image: "tx/35" } }` for /og/tx/35.png.
 */
export function getStaticPaths(): { params: { image: string } }[] {
  // Runs once per build: stop it rather than publish 487 cards without text.
  assertFontsLoad();
  return [...cards().keys()].map((image) => ({ params: { image } }));
}

/**
 * Draw one preview image at build time.
 * @param context - Astro's endpoint context.
 * @param context.params - Route params; `image` names the card, such as `tx/35`.
 * @returns The PNG, or a 404 for an unknown name.
 */
export const GET: APIRoute = ({ params }) => {
  const draw = cards().get(params.image ?? "");
  if (!draw) {
    return new Response("Not found", { status: 404 });
  }
  return new Response(new Uint8Array(renderPng(draw())), { headers: { "Content-Type": "image/png" } });
};
