import { describe, expect, it } from "vitest";

import { districts, outline, states } from "./data";
import { closeups } from "./closeups";
import {
  cityTierCss,
  cityTiers,
  closeupCityTiers,
  districtCityTiers,
  labelBox,
  labelText,
  placeCities,
  type City,
  type CityMark,
  type CityTier,
} from "./cities";

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

  it("keeps labels inside a viewBox that doesn't start at 0", () => {
    // A label to the right of x = 60 runs past 100; on the left it fits from -100.
    expect(placeCities([city("El Paso", 60, 0)], "-100 -50 200 100", FONT, 8)[0]?.side).toBe("left");
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
      const rules = cityTierCss(tiers, "state").split("\n");
      // One rule per tier, each either unconditional or under a non-empty container query.
      const valid = /^(@container \((min|max)-width: [\d.]+px\)( and \(max-width: [\d.]+px\))? \{ )?svg \.cities\.state-tier-\d \{ display: inline; \}( \})?$/;
      return rules.length === tiers.length && rules.every((r) => valid.test(r)) ? [] : [s.state];
    });
    expect(states).toHaveLength(50); // anchor
    expect(broken).toEqual([]);
  });

  it("names each map's tiers apart, so a page's two maps don't show each other's tiers", () => {
    expect(cityTierCss(districtCityTiers("LA-02"), "district")).toContain(".district-tier-0 {");
  });

  it("outranks the scoped hide rule (.cities plus an attribute) by specificity, not order", () => {
    // Two classes and an element beat two classes (Astro scopes .cities with an attribute).
    expect(cityTierCss(cityTiers("TN"), "state")).toMatch(/^@container [^{]+\{ svg \.cities\.state-tier-0 \{/);
    expect(cityTierCss(districtCityTiers("LA-02"), "district")).not.toContain("state-tier");
  });
});

describe("districtCityTiers", () => {
  it("marks New Orleans on its district's outline", () => {
    expect(districtCityTiers("LA-02").length).toBeGreaterThanOrEqual(2); // anchor
    for (const tier of districtCityTiers("LA-02")) {
      expect(tier.marks[0]?.name).toBe("New Orleans");
    }
  });

  it("marks at least one city on every district at every width", () => {
    expect(districts).toHaveLength(435); // anchor: real data
    expect(districts.filter((d) => districtCityTiers(d.id).length === 0)).toEqual([]);
    const empty = districts.flatMap((d) =>
      districtCityTiers(d.id)
        .filter((t) => t.marks.length === 0)
        .map((t) => `${d.id}@${t.min}`),
    );
    expect(empty).toEqual([]);
  });

  it("never overlaps two labels, or a label and a dot, on any district at any width", () => {
    let marked = 0;
    const clashes: string[] = [];
    for (const d of districts) {
      for (const tier of districtCityTiers(d.id)) {
        marked += tier.marks.length;
        const boxes = tier.marks.map((m) => labelBox(m, tier.fontSize));
        boxes.forEach((box, i) =>
          tier.marks.forEach((m, j) => {
            if (i !== j && overlaps(box, [m.x - 1, m.y - 1, m.x + 1, m.y + 1])) clashes.push(d.id);
            if (i < j && overlaps(box, boxes[j] ?? [])) clashes.push(d.id);
          }),
        );
      }
    }
    expect(marked).toBeGreaterThan(2000); // anchor
    expect(clashes).toEqual([]);
  });

  it("lets labels use the whole square box around a thin district, not just its strip", () => {
    // FL-25 is a coastal strip 203 units wide in a 1000-unit square.
    for (const tier of districtCityTiers("FL-25")) expect(tier.marks.length).toBeGreaterThanOrEqual(5);
  });

  it("sizes labels for the outline's square box, whose side spans 1000 map units", () => {
    // Anchor: some districts are taller than wide, where the longer side is the height.
    const tall = districts.filter((d) => {
      const [, , w, h] = outline(d.id, "page").viewBox.split(" ").map(Number) as [number, number, number, number];
      return h > w;
    });
    expect(tall.length).toBeGreaterThan(50);
    const off = districts.flatMap((d) =>
      districtCityTiers(d.id)
        .filter((t) => Math.abs(t.fontSize - (11 * 1000) / t.ref) > 1e-6)
        .map(() => d.id),
    );
    expect(off).toEqual([]);
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

function clashes(tier: CityTier): boolean {
  const boxes = tier.marks.map((m) => labelBox(m, tier.fontSize));
  return boxes.some(
    (box, i) =>
      boxes.some((other, j) => i < j && overlaps(box, other)) ||
      tier.marks.some((m, j) => i !== j && overlaps(box, [m.x - 1, m.y - 1, m.x + 1, m.y + 1])),
  );
}

describe("closeupCityTiers", () => {
  const all = states.flatMap((s) => closeups(s.state).map((c) => ({ state: s.state, c })));

  function losAngeles() {
    const [la, central] = closeups("CA");
    if (!la || !central) throw new Error("California has no Los Angeles close-ups");
    return { la, central };
  }

  it("marks Los Angeles and its neighbors in the Los Angeles close-ups", () => {
    const { la, central } = losAngeles();
    for (const c of [la, central]) {
      for (const tier of closeupCityTiers("CA", c)) {
        expect(tier.marks.map((m) => m.name)).toContain("Los Angeles");
      }
    }
    const widest = closeupCityTiers("CA", la).at(-1)?.marks.map((m) => m.name) ?? [];
    expect(widest).toEqual(expect.arrayContaining(["Los Angeles", "Long Beach", "Anaheim"]));
  });

  it("puts a city where the close-up draws the same spot", () => {
    const { la } = losAngeles();
    const [x0, y0] = la.mapBox;
    const city = cityTiers("CA").at(-1)?.marks.find((m) => m.name === "Los Angeles");
    const mark = closeupCityTiers("CA", la).at(-1)?.marks.find((m) => m.name === "Los Angeles");
    expect(mark?.x).toBeCloseTo(((city?.x ?? 0) - x0) * la.zoom, 5);
    expect(mark?.y).toBeCloseTo(((city?.y ?? 0) - y0) * la.zoom, 5);
  });

  it("marks at least one city in every close-up at every width, with no labels overlapping", () => {
    expect(all).toHaveLength(31); // anchor: every close-up
    expect(all.filter(({ state, c }) => closeupCityTiers(state, c).length === 0).map(({ c }) => c.name)).toEqual([]);
    const empty = all.flatMap(({ state, c }) =>
      closeupCityTiers(state, c)
        .filter((t) => t.marks.length === 0)
        .map((t) => `${c.name}@${t.min}`),
    );
    expect(empty).toEqual([]);
    const clashing = all.filter(({ state, c }) => closeupCityTiers(state, c).some(clashes)).map(({ c }) => c.name);
    expect(clashing).toEqual([]);
  });

  it("only marks cities inside the close-up", () => {
    const outside = all.flatMap(({ state, c }) => {
      const [, , w, h] = c.viewBox.split(" ").map(Number) as [number, number, number, number];
      return closeupCityTiers(state, c).flatMap((t) =>
        t.marks.filter((m) => m.x < 0 || m.y < 0 || m.x > w || m.y > h).map((m) => `${c.name}: ${m.name}`),
      );
    });
    expect(outside).toEqual([]);
  });
});
