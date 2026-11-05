/** Where a visitor's light or dark choice is saved, in localStorage. */
export const THEME_KEY = "theme";

/** The page's root element, as far as the theme needs it. */
export interface ThemeRoot {
  dataset: Record<string, string | undefined>;
}

/** The light/dark switch (a button with role="switch"), as far as the theme needs it. */
export interface ThemeButton {
  hidden: boolean;
  setAttribute(name: string, value: string): void;
  addEventListener(type: "click", listener: () => void): void;
}

// Both functions run as inline scripts (Base.astro writes them out with toString), so they
// must not use anything from outside themselves, THEME_KEY included.

/**
 * Switch the page to dark if the visitor chose dark before. Runs in the head, before the
 * page draws, so a dark page never flashes light first. Light is the default.
 * @param root - The page's root element.
 * @param storage - Returns localStorage; calling it can throw where storage is blocked.
 */
export function applySavedTheme(root: ThemeRoot, storage: () => Pick<Storage, "getItem">): void {
  try {
    if (storage().getItem("theme") === "dark") {
      root.dataset.theme = "dark";
    }
  } catch {
    // Storage is blocked: stay light.
  }
}

/**
 * Show the light/dark toggle and make it switch and remember the theme.
 * @param root - The page's root element.
 * @param button - The toggle, hidden until this runs so it never shows without JavaScript.
 * @param storage - Returns localStorage; calling it can throw where storage is blocked.
 */
export function setupThemeToggle(
  root: ThemeRoot,
  button: ThemeButton | null,
  storage: () => Pick<Storage, "getItem" | "setItem">,
): void {
  if (!button) {
    return;
  }
  const sync = () => button.setAttribute("aria-checked", String(root.dataset.theme === "dark"));
  button.addEventListener("click", () => {
    const dark = root.dataset.theme !== "dark";
    if (dark) {
      root.dataset.theme = "dark";
    } else {
      delete root.dataset.theme;
    }
    sync();
    try {
      storage().setItem("theme", dark ? "dark" : "light");
    } catch {
      // Storage is blocked: the switch still works for this page.
    }
  });
  sync();
  button.hidden = false;
}
