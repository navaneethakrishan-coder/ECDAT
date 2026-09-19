/**
 * The theme system: one piece of state, persisted, applied to the
 * document element where the CSS tokens hang off it.
 *
 * What matters here is not that a class name changed but that the
 * *document* carries the theme, because that attribute is what both the
 * stylesheet and the 3D scene read.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { describe, expect, it, vi } from "vitest";

import { STORAGE_KEY, useTheme } from "./ThemeContext";
import { ThemeProvider } from "./ThemeProvider";
import { ThemeToggle } from "./ThemeToggle";

function Harness({ onTheme }) {
  const { theme } = useTheme();
  useEffect(() => {
    onTheme?.(theme, document.documentElement.dataset.theme);
  }, [theme, onTheme]);
  return (
    <>
      <span data-testid="theme">{theme}</span>
      <ThemeToggle />
    </>
  );
}

describe("theme state", () => {
  it("starts in dark, the product's original appearance", () => {
    render(
      <ThemeProvider>
        <Harness />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("theme")).toHaveTextContent("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("restores the saved preference on reload", () => {
    window.localStorage.setItem(STORAGE_KEY, "light");

    render(
      <ThemeProvider>
        <Harness />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("theme")).toHaveTextContent("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("falls back to dark when the stored value is not a theme", () => {
    window.localStorage.setItem(STORAGE_KEY, "solarized");

    render(
      <ThemeProvider>
        <Harness />
      </ThemeProvider>,
    );

    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("persists the choice when the user switches", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <Harness />
      </ThemeProvider>,
    );

    await user.click(screen.getByRole("button"));

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("light");

    await user.click(screen.getByRole("button"));

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });

  it("still applies a theme it cannot persist", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked site data");
    });
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <Harness />
      </ThemeProvider>,
    );
    await user.click(screen.getByRole("button"));

    // A private window cannot remember the choice, but the session still honours it.
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("writes the attribute before anything downstream reacts to the change", async () => {
    // The 3D scene repaints from the --env-* tokens in an effect of its
    // own, and React runs a child's effects before its parent's. If the
    // attribute were only written in the provider's effect, that repaint
    // would read the theme being left behind.
    const seen = [];
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <Harness onTheme={(theme, onDocument) => seen.push({ theme, onDocument })} />
      </ThemeProvider>,
    );
    await user.click(screen.getByRole("button"));

    for (const entry of seen) {
      expect(entry.onDocument).toBe(entry.theme);
    }
  });

  it("sets colorScheme so native controls follow the theme", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <Harness />
      </ThemeProvider>,
    );

    expect(document.documentElement.style.colorScheme).toBe("dark");
    await user.click(screen.getByRole("button"));
    expect(document.documentElement.style.colorScheme).toBe("light");
  });
});

describe("the theme switch", () => {
  it("names both the current mode and the one it switches to", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    // An icon alone never says whether it shows the state or the action.
    const toggle = screen.getByRole("button");
    expect(toggle).toHaveAccessibleName("Switch to light mode (currently dark mode)");
    expect(toggle).toHaveTextContent("Light mode");

    await user.click(toggle);

    expect(screen.getByRole("button")).toHaveAccessibleName(
      "Switch to dark mode (currently light mode)",
    );
  });

  it("is reachable and operable from the keyboard", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    await user.tab();
    expect(screen.getByRole("button")).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
