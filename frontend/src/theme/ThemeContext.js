import { createContext, useContext } from "react";

/**
 * Application theme: "dark" (the original ECDAT console) or "light".
 *
 * The theme is one piece of state at the app root. Components never
 * branch on it -- they use the CSS custom properties in App.css, which
 * are redefined under `:root[data-theme="light"]`. That is what keeps a
 * second theme from becoming a second implementation of the UI.
 */
export const ThemeContext = createContext({
  theme: "dark",
  setTheme: () => {},
  toggleTheme: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

export const THEMES = ["dark", "light"];
export const STORAGE_KEY = "ecdat.theme";
