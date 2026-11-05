/** Rows in the state tile map. */
export const TILE_ROWS = 8;
/** Columns in the state tile map. */
export const TILE_COLUMNS = 11;

/**
 * Each state's cell in a tile map of the US: one equal square per state, placed roughly where
 * the state is, so a reader can find a state by where it is rather than by name. Alaska and
 * Hawaii sit at the left, as on most US maps. Zero-based [row, column].
 */
export const STATE_TILES: Record<string, [number, number]> = {
  AK: [0, 0],
  ME: [0, 10],
  WI: [1, 5],
  VT: [1, 9],
  NH: [1, 10],
  WA: [2, 0],
  ID: [2, 1],
  MT: [2, 2],
  ND: [2, 3],
  MN: [2, 4],
  IL: [2, 5],
  MI: [2, 6],
  NY: [2, 8],
  MA: [2, 9],
  OR: [3, 0],
  NV: [3, 1],
  WY: [3, 2],
  SD: [3, 3],
  IA: [3, 4],
  IN: [3, 5],
  OH: [3, 6],
  PA: [3, 7],
  NJ: [3, 8],
  CT: [3, 9],
  RI: [3, 10],
  CA: [4, 0],
  UT: [4, 1],
  CO: [4, 2],
  NE: [4, 3],
  MO: [4, 4],
  KY: [4, 5],
  WV: [4, 6],
  VA: [4, 7],
  MD: [4, 8],
  DE: [4, 9],
  AZ: [5, 1],
  NM: [5, 2],
  KS: [5, 3],
  AR: [5, 4],
  TN: [5, 5],
  NC: [5, 6],
  SC: [5, 7],
  OK: [6, 3],
  LA: [6, 4],
  MS: [6, 5],
  AL: [6, 6],
  GA: [6, 7],
  HI: [7, 0],
  TX: [7, 3],
  FL: [7, 8],
};
