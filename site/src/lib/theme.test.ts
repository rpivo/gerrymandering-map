import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it } from "vitest";

import css from "../styles/global.css?raw";
import Base from "../layouts/Base.astro";
import { applySavedTheme, setupThemeToggle, THEME_KEY, type ThemeButton } from "./theme";

function memoryStorage(initial: Record<string, string> = {}) {
  const items = { ...initial };
  return {
    items,
    getItem: (key: string) => items[key] ?? null,
    setItem: (key: string, value: string) => {
      items[key] = value;
    },
  };
}

function fakeButton() {
  const attributes: Record<string, string> = {};
  let click = () => {};
  const button: ThemeButton & { attributes: Record<string, string>; click: () => void } = {
    hidden: true,
    attributes,
    setAttribute: (name, value) => {
      attributes[name] = value;
    },
    addEventListener: (_type, listener) => {
      click = listener;
    },
    click: () => click(),
  };
  return button;
}

const blocked = () => {
  throw new Error("SecurityError: storage is blocked");
};

describe("the stylesheet", () => {
  it("is light unless the page asks for dark, whatever the device prefers", () => {
    expect(css).not.toContain("prefers-color-scheme");
    expect(css).toMatch(/:root\s*\{\s*color-scheme:\s*light;/);
    expect(css).toMatch(/:root\[data-theme="dark"\]\s*\{\s*color-scheme:\s*dark;/);
  });
});

describe("applySavedTheme", () => {
  it("applies a saved dark choice", () => {
    const root = { dataset: {} as Record<string, string | undefined> };
    applySavedTheme(root, () => memoryStorage({ [THEME_KEY]: "dark" }));
    expect(root.dataset.theme).toBe("dark");
  });

  it("stays light with no saved choice, or a light one", () => {
    for (const saved of [{}, { [THEME_KEY]: "light" }]) {
      const root = { dataset: {} as Record<string, string | undefined> };
      applySavedTheme(root, () => memoryStorage(saved));
      expect(root.dataset.theme).toBeUndefined();
    }
  });

  it("stays light when storage is blocked, instead of breaking the page", () => {
    const root = { dataset: {} as Record<string, string | undefined> };
    expect(() => applySavedTheme(root, blocked)).not.toThrow();
    expect(root.dataset.theme).toBeUndefined();
  });

  it("can run as an inline script: it uses nothing from outside itself", () => {
    const root = { dataset: {} as Record<string, string | undefined> };
    new Function("root", "storage", `(${applySavedTheme.toString()})(root, storage)`)(root, () =>
      memoryStorage({ theme: "dark" }),
    );
    expect(root.dataset.theme).toBe("dark");
  });
});

describe("setupThemeToggle", () => {
  it("shows the switch and says whether dark mode is on", () => {
    const button = fakeButton();
    setupThemeToggle({ dataset: { theme: "dark" } }, button, () => memoryStorage());
    expect(button.hidden).toBe(false);
    expect(button.attributes["aria-checked"]).toBe("true");
  });

  it("switches and remembers the choice each way", () => {
    const root = { dataset: {} as Record<string, string | undefined> };
    const button = fakeButton();
    const storage = memoryStorage();
    setupThemeToggle(root, button, () => storage);
    expect(button.attributes["aria-checked"]).toBe("false");
    button.click();
    expect(root.dataset.theme).toBe("dark");
    expect(button.attributes["aria-checked"]).toBe("true");
    expect(storage.items[THEME_KEY]).toBe("dark");
    button.click();
    expect(root.dataset.theme).toBeUndefined();
    expect(button.attributes["aria-checked"]).toBe("false");
    expect(storage.items[THEME_KEY]).toBe("light");
  });

  it("still switches when storage is blocked, just without remembering", () => {
    const root = { dataset: {} as Record<string, string | undefined> };
    const button = fakeButton();
    setupThemeToggle(root, button, blocked);
    expect(() => button.click()).not.toThrow();
    expect(root.dataset.theme).toBe("dark");
  });

  it("does nothing on a page without the button", () => {
    expect(() => setupThemeToggle({ dataset: {} }, null, () => memoryStorage())).not.toThrow();
  });
});

describe("the layout", () => {
  it("applies a saved theme in the head, before the page draws, and has a hidden toggle for scripts to show", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, { props: { title: "T", description: "D" } });
    const head = html.slice(0, html.indexOf("</head>"));
    expect(head).toMatch(/<script>[^<]*getItem\("theme"\)/);
    expect(html).toMatch(/<button[^>]*class="theme-toggle"[^>]*hidden/);
    expect(html).toMatch(/<button[^>]*type="button"/);
    expect(html).toMatch(/<button[^>]*role="switch"/);
    expect(html).toMatch(/<button[^>]*aria-checked="false"/);
    expect(html).toMatch(/<button[^>]*aria-label="Dark mode"/);
  });

  it("shows a sun and a moon, hidden from screen readers since the label says it", async () => {
    const container = await AstroContainer.create();
    const html = await container.renderToString(Base, { props: { title: "T", description: "D" } });
    const start = html.lastIndexOf("<button", html.indexOf('class="theme-toggle"'));
    const button = html.slice(start, html.indexOf("</button>", start));
    const icons = button.match(/<svg[^>]*>/g) ?? [];
    expect(icons).toHaveLength(2);
    expect(icons.every((svg) => svg.includes('aria-hidden="true"'))).toBe(true);
    expect(button).toContain('class="icon sun"');
    expect(button).toContain('class="icon moon"');
    expect(button.replace(/<[^>]+>/g, "").trim()).toBe(""); // no visible text, just the icons
  });
});
