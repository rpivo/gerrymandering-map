/** What the home grid knows about each district card. */
export interface Card {
  id: string;
  state: string;
  stateName: string;
  number: number | null;
  score: number | null;
  rank: number | null;
}

/** The grid's filter controls. */
export interface Filters {
  query: string;
  state: string;
  includeAtLarge: boolean;
}

export type SortKey = "irregular" | "compact" | "state";

/**
 * Normalize a search query.
 * @param query - What the visitor typed.
 * @returns The query lowercased, without spaces or hyphens.
 */
export function normalizeQuery(query: string): string {
  return query.toLowerCase().replace(/[\s-]+/g, "");
}

/**
 * List the ways a visitor might type this district's ID, normalized.
 * @param card - A district card.
 * @returns For example ["tx1", "tx01"], or ["wyal"] for at-large.
 */
function idKeys(card: Card): string[] {
  const state = card.state.toLowerCase();
  if (card.number === null) {
    return [`${state}al`];
  }
  return [`${state}${card.number}`, `${state}${String(card.number).padStart(2, "0")}`];
}

/**
 * Check whether a card passes the filters.
 * @param card - A district card.
 * @param filters - The current filters.
 * @returns True if the card should be shown.
 */
export function matches(card: Card, filters: Filters): boolean {
  if (filters.state && card.state !== filters.state) {
    return false;
  }
  if (!filters.includeAtLarge && card.number === null) {
    return false;
  }
  const query = normalizeQuery(filters.query);
  if (!query) {
    return true;
  }
  return (
    idKeys(card).includes(query) ||
    query === card.state.toLowerCase() ||
    normalizeQuery(card.stateName).includes(query)
  );
}

/**
 * Return a sort key from the national rank, putting unranked (at-large) districts last.
 * @param card - A district card.
 * @param direction - 1 for most irregular first, -1 for most compact first.
 * @returns The key; Infinity for at-large districts.
 */
function rankOrLast(card: Card, direction: 1 | -1): number {
  return card.rank === null ? Number.POSITIVE_INFINITY : direction * card.rank;
}

/**
 * Sort cards without changing the input.
 * @param cards - District cards.
 * @param key - How to sort.
 * @returns A new sorted array.
 */
export function sortCards(cards: Card[], key: SortKey): Card[] {
  const byState = (a: Card, b: Card) =>
    a.stateName.localeCompare(b.stateName) || (a.number ?? 0) - (b.number ?? 0);
  const compare = {
    irregular: (a: Card, b: Card) => rankOrLast(a, 1) - rankOrLast(b, 1) || byState(a, b),
    compact: (a: Card, b: Card) => rankOrLast(a, -1) - rankOrLast(b, -1) || byState(a, b),
    state: byState,
  }[key];
  return [...cards].sort(compare);
}
