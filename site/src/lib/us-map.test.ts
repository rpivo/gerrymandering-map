import { describe, expect, it } from "vitest";

import { states } from "./data";
import { CALLOUT_STATES, callouts, usMap } from "./us-map";

describe("usMap", () => {
  it("draws and labels every state", () => {
    const map = usMap();
    // Anchor: 50 states, so an empty map can't pass vacuously.
    expect(states).toHaveLength(50);
    expect(states.filter((s) => !map.paths[s.state] || !map.labels[s.state])).toEqual([]);
  });
});

describe("callouts", () => {
  const map = { viewBox: "0 0 1000 600", paths: {}, labels: {} as Record<string, number[]> };
  // Squeezed together, as the real states nearly are.
  CALLOUT_STATES.forEach((s, i) => (map.labels[s] = [950, 100 + i * 5]));

  it("stacks one box per small state, north to south, right of the map", () => {
    const boxes = callouts(map);
    expect(boxes.map((b) => b.state)).toEqual(CALLOUT_STATES);
    expect(boxes.every((b) => b.x > 1000)).toBe(true);
    expect(boxes[0]?.y).toBe(100); // the first sits level with its state
  });

  it("keeps boxes from overlapping when their states are close together", () => {
    const ys = callouts(map).map((b) => b.y);
    const gaps = ys.slice(1).map((y, i) => y - (ys[i] ?? 0));
    expect(gaps).toHaveLength(CALLOUT_STATES.length - 1);
    expect(Math.min(...gaps)).toBeGreaterThanOrEqual(32);
  });

  it("starts each leader line at its state's label", () => {
    expect(callouts(map).every((b) => b.from === map.labels[b.state])).toBe(true);
  });
});
