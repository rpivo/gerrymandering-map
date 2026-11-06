import type { APIRoute } from "astro";

import { type ZipGroup, zipIndex } from "../../lib/zip-search";

/**
 * List one index file per group of ZIP codes sharing their first three digits.
 * @returns Each group's path (`zip/782.json`) with its ZIP codes as props.
 */
export function getStaticPaths(): { params: { prefix: string }; props: { group: ZipGroup } }[] {
  return [...zipIndex()].map(([prefix, group]) => ({ params: { prefix }, props: { group } }));
}

/**
 * Write a group's ZIP codes, each with its districts and their percent, largest first.
 * @param context The route's context.
 * @param context.props The group, from getStaticPaths.
 * @returns The group as JSON.
 */
export const GET: APIRoute = ({ props }) =>
  new Response(JSON.stringify((props as { group: ZipGroup }).group), {
    headers: { "Content-Type": "application/json" },
  });
