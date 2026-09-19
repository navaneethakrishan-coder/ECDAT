import { useCallback, useLayoutEffect, useMemo, useState } from "react";

import { STORAGE_KEY, THEMES, ThemeContext } from "./ThemeContext";

/**
 * Owns the theme and writes it to the document element, where the CSS
 * token overrides hang off `[data-theme]`.
 *
 * Dark is the default and the product's original appearance, so an
 * unreadable or missing stored value falls back to dark rather than to
 * the OS preference -- ECDAT's identity is the dark console, and a user
 * who has never chosen should see it.
 */
function readStoredTheme() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return THEMES.includes(stored) ? stored : null;
  } catch {
    // Private windows and blocked site data throw on access.
    return null;
  }
}

function applyToDocument(theme) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  // Lets the browser theme form controls, scrollbars and the canvas
  // backdrop correctly without any extra styling.
  root.style.colorScheme = theme;
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => readStoredTheme() || "dark");

  // Before paint, so a stored light preference never flashes dark first.
  useLayoutEffect(() => {
    applyToDocument(theme);

    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // A theme that cannot be persisted still applies for this session.
    }
  }, [theme]);

  const setTheme = useCallback((next) => {
    const value = THEMES.includes(next) ? next : "dark";
    // Written here rather than left to the effect above.
    //
    // React runs a child's effects before its parent's, and the 3D scene
    // repaints itself from the `--env-*` tokens in an effect of its own.
    // If the attribute were only set in this provider's effect, that
    // repaint would read the theme we just left and paint the scene in
    // the wrong theme until something else touched it.
    applyToDocument(value);
    setThemeState(value);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  const value = useMemo(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
