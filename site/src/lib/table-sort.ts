/** A column a state's district table can be sorted by. */
export type TableSortKey = "district" | "score" | "rank";

/** A sort order, named as `aria-sort` names it. */
export interface TableSort {
  key: TableSortKey;
  dir: "ascending" | "descending";
}

/** What a district row sorts on; null for an at-large district's number, score and rank. */
export interface SortRow {
  number: number | null;
  score: number | null;
  rank: number | null;
}

/** The order a column starts in: district 1 first, most irregular first, 1st least compact first. */
const NATURAL: Record<TableSortKey, TableSort["dir"]> = {
  district: "ascending",
  score: "descending",
  rank: "ascending",
};

const FIELD: Record<TableSortKey, keyof SortRow> = { district: "number", score: "score", rank: "rank" };

/**
 * Sort rows without changing the input.
 * @param rows District rows.
 * @param sort The column and direction.
 * @returns A new array. Rows with no value in the column (an at-large district) go last either way.
 */
export function sortRows<T extends SortRow>(rows: T[], sort: TableSort): T[] {
  const field = FIELD[sort.key];
  const sign = sort.dir === "ascending" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = a[field];
    const y = b[field];
    if (x === null || y === null) return (x === null ? 1 : 0) - (y === null ? 1 : 0);
    return sign * (x - y) || (a.number ?? 0) - (b.number ?? 0);
  });
}

/**
 * Work out the order after a column heading is clicked.
 * @param current The order now.
 * @param clicked The column clicked.
 * @returns The current column reversed, or a new column in its natural order.
 */
export function nextSort(current: TableSort, clicked: TableSortKey): TableSort {
  if (current.key === clicked) {
    return { key: clicked, dir: current.dir === "ascending" ? "descending" : "ascending" };
  }
  return { key: clicked, dir: NATURAL[clicked] };
}
