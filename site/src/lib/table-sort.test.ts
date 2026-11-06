import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it } from "vitest";

import StatePage from "../pages/[state]/index.astro";
import { states } from "./data";
import { nextSort, type SortRow, sortRows } from "./table-sort";

const row = (number: number | null, score: number | null, rank: number | null): SortRow => ({ number, score, rank });
const A = row(1, 27, 334);
const B = row(2, 95, 13);
const C = row(3, 50, 206);
const ids = (rows: SortRow[]) => rows.map((r) => r.number);

describe("sorting a state's districts", () => {
  it("sorts by district number, score or national rank, either way", () => {
    expect(ids(sortRows([C, A, B], { key: "district", dir: "ascending" }))).toEqual([1, 2, 3]);
    expect(ids(sortRows([A, B, C], { key: "district", dir: "descending" }))).toEqual([3, 2, 1]);
    expect(ids(sortRows([A, B, C], { key: "score", dir: "descending" }))).toEqual([2, 3, 1]);
    expect(ids(sortRows([A, B, C], { key: "rank", dir: "ascending" }))).toEqual([2, 3, 1]);
  });

  it("keeps an unscored at-large district last whichever way it's sorted", () => {
    const AL = row(null, null, null);
    expect(sortRows([AL, A, B], { key: "score", dir: "descending" }).at(-1)).toBe(AL);
    expect(sortRows([AL, A, B], { key: "score", dir: "ascending" }).at(-1)).toBe(AL);
    expect(sortRows([AL, A, B], { key: "rank", dir: "ascending" }).at(-1)).toBe(AL);
  });

  it("starts a new column in its natural order and flips the current one", () => {
    const start = { key: "district", dir: "ascending" } as const;
    expect(nextSort(start, "district")).toEqual({ key: "district", dir: "descending" });
    expect(nextSort(start, "score")).toEqual({ key: "score", dir: "descending" });
    expect(nextSort(start, "rank")).toEqual({ key: "rank", dir: "ascending" });
  });
});

describe("a state page's district table", () => {
  it("has a sort button in each column heading, sorted by district to start", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(StatePage, { props: { state: states.find((s) => s.state === "NJ") } });
    const head = html.slice(html.indexOf("<thead"), html.indexOf("</thead>"));
    for (const key of ["district", "score", "rank"]) {
      expect(head).toMatch(new RegExp(`<th[^>]*data-sort-key="${key}"[^>]*>\\s*<button[^>]*type="button"`));
    }
    expect(head).toMatch(/<th[^>]*aria-sort="ascending"[^>]*data-sort-key="district"|<th[^>]*data-sort-key="district"[^>]*aria-sort="ascending"/);
    const body = html.slice(html.indexOf("<tbody"), html.indexOf("</tbody>"));
    expect(body.match(/<tr[^>]*data-number="\d+"[^>]*data-score="\d+"[^>]*data-rank="\d+"/g)).toHaveLength(12);
  });
});
