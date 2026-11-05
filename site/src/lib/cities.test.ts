import { describe, expect, it } from "vitest";

import { states } from "./data";
import { cityTierCss, cityTiers, labelBox, labelText, placeCities, type City, type CityMark } from "./cities";

const VIEW = "0 0 1000 500";
const FONT = 20;

function city(name: string, x: number, y: number): City {
  return { name, pop: 1000, x, y };
}

function overlaps(a: number[], b: number[]): boolean {
  const [ax0, ay0, ax1, ay1] = a as [number, number, number, number];
  const [bx0, by0, bx1, by1] = b as [number, number, number, number];
  return ax0 < bx1 && bx0 < ax1 && ay0 < by1 && by0 < ay1;
}

describe("placeCities", () => {
  it("labels a city to the right of its dot", () => {
    expect(placeCities([city("Austin", 400, 250)], VIEW, FONT, 8)).toEqual([
      { name: "Austin", x: 400, y: 250, side: "right" },
    ]);
  });

  it("puts the label on the left when the right would run off the map", () => {
    const [mark] = placeCities([city("El Paso", 990, 250)], VIEW, FONT, 8);
    expect(mark?.side).toBe("left");
  });

  it("leaves out a city whose label fits on neither side", () => {
    // 30 characters at 20 units is far wider than either side of a dot in a 300-wide map.
    const long = city("A very long place name for here", 150, 50);
    expect(placeCities([long], "0 0 300 100", FONT, 8)).toEqual([]);
  });

  it("leaves out a smaller city that would collide with a bigger one, but keeps a clear one", () => {
    const marks = placeCities(
      [city("Dallas", 400, 250), city("Fort Worth", 430, 252), city("Houston", 700, 400)],
      VIEW,
      FONT,
      8,
    );
    expect(marks.map((m) => m.name)).toEqual(["Dallas", "Houston"]);
  });

  it("tries the other side before giving up on a crowded city", () => {
    // Arlington is far enough from Dallas to mark, but its right side would cover Dallas's label.
    const marks = placeCities([city("Dallas", 400, 250), city("Arlington", 340, 262)], VIEW, FONT, 8);
    expect(marks.find((m) => m.name === "Arlington")?.side).toBe("left");
  });

  it("puts the label above, then below, when neither side fits", () => {
    // "Midland" is 84 units wide at 20: too wide for either side of a dot in a 120-wide map.
    expect(placeCities([city("Midland", 60, 100)], "0 0 120 200", FONT, 8)[0]?.side).toBe("above");
    expect(placeCities([city("Midland", 60, 15)], "0 0 120 200", FONT, 8)[0]?.side).toBe("below");
  });

  it("puts a label on a side that leaves room for a bigger city still to come", () => {
    // Dallas's label on the right would cover Fort Worth's dot; on the left it's clear.
    const marks = placeCities([city("Dallas", 400, 250), city("Fort Worth", 470, 250)], VIEW, FONT, 8);
    expect(marks.map((m) => [m.name, m.side])).toEqual([["Dallas", "left"], ["Fort Worth", "right"]]);
  });

  it("skips a suburb right beside a marked city, which adds little as a landmark", () => {
    // Irving's labels clear Dallas's, but its dot is under 2 label heights from Dallas's.
    const marks = placeCities(
      [city("Dallas", 400, 250), city("Irving", 375, 275), city("Waco", 400, 320)],
      VIEW,
      FONT,
      8,
    );
    expect(marks.map((m) => m.name)).toEqual(["Dallas", "Waco"]);
  });

  it("marks at most max cities, largest first", () => {
    const many = Array.from({ length: 12 }, (_, i) => city(`C${i}`, 50 + i * 80, 40 + (i % 2) * 400));
    expect(placeCities(many, VIEW, FONT, 5).map((m) => m.name)).toEqual(["C0", "C1", "C2", "C3", "C4"]);
  });
});

describe("cityTierCss", () => {
  it("has a valid rule showing every tier of every state", () => {
    const broken = states.flatMap((s) => {
      const tiers = cityTiers(s.state);
      const rules = cityTierCss(tiers).split("\n");
      // One rule per tier, each either unconditional or under a non-empty container query.
      const valid = /^(@container \((min|max)-width: [\d.]+px\)( and \(max-width: [\d.]+px\))? \{ )?\.map-frame \.tier-\d \{ display: inline; \}( \})?$/;
      return rules.length === tiers.length && rules.every((r) => valid.test(r)) ? [] : [s.state];
    });
    expect(states).toHaveLength(50); // anchor
    expect(broken).toEqual([]);
  });
});

describe("cityTiers", () => {
  it("gives every state at least one marked city at every width it can be drawn", () => {
    expect(states).toHaveLength(50); // anchor: real data, so the loop can't pass empty
    expect(states.filter((s) => cityTiers(s.state).length === 0)).toEqual([]);
    const empty = states.flatMap((s) =>
      cityTiers(s.state)
        .filter((t) => t.marks.length === 0)
        .map((t) => `${s.state}@${t.min}`),
    );
    expect(empty).toEqual([]);
  });

  it("marks 10 cities on every state's map at its widest", () => {
    const short = states
      .map((s) => ({ state: s.state, marks: cityTiers(s.state).at(-1)?.marks.length ?? 0 }))
      .filter((s) => s.marks < 10);
    expect(states).toHaveLength(50); // anchor
    expect(short).toEqual([]);
  });

  it("never overlaps two labels, or a label and a dot, at any width", () => {
    const clashes: string[] = [];
    let marked = 0;
    for (const s of states) {
      for (const tier of cityTiers(s.state)) {
        marked += tier.marks.length;
        const boxes = tier.marks.map((m: CityMark) => labelBox(m, tier.fontSize));
        const dots = tier.marks.map((m) => [m.x - 1, m.y - 1, m.x + 1, m.y + 1]);
        boxes.forEach((box, i) => {
          boxes.forEach((other, j) => {
            if (i < j && overlaps(box, other)) clashes.push(`${s.state}@${tier.min}`);
          });
          dots.forEach((dot, j) => {
            if (i !== j && overlaps(box, dot)) clashes.push(`${s.state}@${tier.min} dot`);
          });
        });
      }
    }
    expect(marked).toBeGreaterThan(100); // anchor: plenty of marks were checked
    expect(clashes).toEqual([]);
  });

  it("marks Michigan's capital and Ann Arbor, rather than Detroit's suburbs", () => {
    for (const tier of cityTiers("MI")) {
      const names = tier.marks.map((m) => m.name);
      expect(names).toEqual(expect.arrayContaining(["Detroit", "Grand Rapids", "Lansing", "Ann Arbor"]));
      expect(names).not.toContain("Sterling Heights");
    }
  });

  it("puts each label's text inside the box it was placed by", () => {
    for (const side of ["right", "left", "above", "below"] as const) {
      const mark: CityMark = { name: "Tulsa", x: 500, y: 250, side };
      const [left, top, right, bottom] = labelBox(mark, FONT) as [number, number, number, number];
      const text = labelText(mark, FONT);
      // The text's anchor point is the box's near edge (or middle) on its vertical center.
      expect(text.y).toBeCloseTo((top + bottom) / 2, 5);
      const expectedX = { start: left, end: right, middle: (left + right) / 2 }[text.anchor];
      expect(text.x).toBeCloseTo(expectedX, 5);
    }
  });

  it("marks Tennessee's big cities on a wide map, and the biggest on a phone-sized one", () => {
    const tiers = cityTiers("TN");
    const widest = (tiers.at(-1)?.marks ?? []).map((m) => m.name);
    expect(widest).toEqual(expect.arrayContaining(["Nashville", "Memphis", "Knoxville", "Chattanooga"]));
    const phone = (tiers[0]?.marks ?? []).map((m) => m.name);
    expect(phone).toEqual(expect.arrayContaining(["Nashville", "Memphis"]));
  });

  it("scales the label size with the map, so a label is about the same size on screen", () => {
    const tiers = cityTiers("CA");
    const [, , width] = "0 0 862 1000".split(" ").map(Number) as [number, number, number];
    for (const tier of tiers) expect(tier.fontSize).toBeCloseTo((11 * width) / tier.ref, 5);
  });

  it("sizes labels for the map's own width when it's never drawn as wide as its tier", () => {
    // New Jersey's map is 525 by 1000 and capped at 512px tall, so it's at most 268.8px wide.
    const [tier] = cityTiers("NJ");
    expect(tier?.ref).toBeCloseTo((512 * 525) / 1000, 5);
    expect(tier?.fontSize).toBeCloseTo((11 * 525) / ((512 * 525) / 1000), 5);
  });

  it("skips widths a state's map is never drawn at", () => {
    // California's map is capped at 32rem tall, so it's never wider than 512 x 862/1000 pixels.
    expect(cityTiers("CA").every((t) => t.min < 512 * 0.862)).toBe(true);
    expect(cityTiers("TN").length).toBeGreaterThan(cityTiers("CA").length);
  });
});
