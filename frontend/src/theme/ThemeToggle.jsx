import { Moon, Sun } from "lucide-react";

import { useTheme } from "./ThemeContext";

/**
 * The theme switch in the console's top edge.
 *
 * It states the mode it is in and the mode it will switch to, rather
 * than relying on the icon alone: an icon-only toggle is the classic
 * case where nobody can tell whether it shows the current state or the
 * action.
 */
export function ThemeToggle({ compact = false }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";
  const next = isDark ? "Light" : "Dark";
  const Icon = isDark ? Sun : Moon;

  return (
    <button
      type="button"
      className={`theme-toggle${compact ? " is-compact" : ""}`}
      onClick={toggleTheme}
      aria-label={`Switch to ${next.toLowerCase()} mode (currently ${theme} mode)`}
      title={`Switch to ${next.toLowerCase()} mode`}
      data-theme-state={theme}
    >
      <Icon size={14} aria-hidden="true" />
      <span className="theme-toggle-label">{next} mode</span>
    </button>
  );
}
