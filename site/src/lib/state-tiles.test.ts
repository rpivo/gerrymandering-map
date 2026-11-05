import { describe, expect, it } from "vitest";

import { states } from "./data";
import { STATE_TILES, TILE_COLUMNS, TILE_ROWS } from "./state-tiles";

describe("STATE_TILES", () => {
  it("places every state once, and nothing else", () => {
    // Anchor: 50 states, so an empty layout can't pass vacuously.
    expect(states).toHaveLength(50);
    expect(Object.keys(STATE_TILES).sort()).toEqual(states.map((s) => s.state).sort());
  });

  it("never puts two states in one cell", () => {
    const cells = Object.values(STATE_TILES).map(([row, col]) => `${row},${col}`);
    expect(new Set(cells).size).toBe(cells.length);
  });

  it("keeps every tile inside the grid", () => {
    const outside = Object.entries(STATE_TILES).filter(
      ([, [row, col]]) => row < 0 || row >= TILE_ROWS || col < 0 || col >= TILE_COLUMNS,
    );
    expect(outside).toEqual([]);
  });

  it("puts states roughly where they are: Washington northwest of Florida, Maine east of California", () => {
    const [waRow, waCol] = STATE_TILES["WA"] ?? [0, 0];
    const [flRow, flCol] = STATE_TILES["FL"] ?? [0, 0];
    expect(waRow).toBeLessThan(flRow);
    expect(waCol).toBeLessThan(flCol);
    expect(STATE_TILES["ME"]?.[1]).toBeGreaterThan(STATE_TILES["CA"]?.[1] ?? 99);
  });
});
