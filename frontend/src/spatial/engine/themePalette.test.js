/**
 * The 3D environment's colours.
 *
 * The scene follows the theme by reading the same `--env-*` tokens the
 * stylesheet defines, so what matters is the wiring: that a tagged
 * material is repainted from the tokens, that an untagged one is left
 * alone (severity and strategy colours encode meaning), and that the
 * GridHelper -- whose colours live in a vertex attribute, not its
 * material -- is repainted too.
 */

import { BufferAttribute, BufferGeometry, Color, LineBasicMaterial, MeshBasicMaterial, MeshStandardMaterial } from "three";
import { beforeEach, describe, expect, it } from "vitest";

import {
  paintThemed,
  paintThemedGrid,
  readEnvPalette,
  refreshPalette,
  roleColor,
  themed,
  themedGrid,
} from "./themePalette";

const DARK = {
  "--env-grid-minor": "#132340",
  "--env-grid-major": "#1f3a66",
  "--env-wall": "#0d1d38",
  "--env-wall-edge": "#2e4a7a",
  "--env-region": "#0f1f3d",
  "--env-band": "#3b5c94",
  "--env-plate": "#0c1a33",
  "--env-track": "#1c2740",
  "--env-pylon": "#0f1a33",
  "--env-pylon-emissive": "#12305a",
  "--env-column": "#2e4066",
  "--env-dust": "#8fb3e6",
  "--env-fog": "#05070f",
  "--env-sky": "#a5b8ff",
  "--env-ground": "#05070f",
  "--env-light-intensity": "1",
  "--env-glow-intensity": "1",
};

const LIGHT = {
  ...DARK,
  "--env-grid-minor": "#ccd8ea",
  "--env-grid-major": "#a8bdda",
  "--env-wall": "#ced9ec",
  "--env-region": "#ffffff",
  "--env-plate": "#ffffff",
  "--env-pylon": "#eef3fb",
  "--env-pylon-emissive": "#000000",
  "--env-fog": "#e7edf7",
  "--env-glow-intensity": "0.55",
};

function useTheme(name, tokens) {
  const root = document.documentElement;
  root.dataset.theme = name;
  for (const [token, value] of Object.entries(tokens)) {
    root.style.setProperty(token, value);
  }
  return refreshPalette();
}

function hex(material) {
  return `#${material.color.getHexString()}`;
}

beforeEach(() => {
  document.documentElement.removeAttribute("style");
});

describe("reading the palette", () => {
  it("reports the theme and every environment role from the tokens", () => {
    const palette = useTheme("light", LIGHT);

    expect(palette.theme).toBe("light");
    expect(palette.fog).toBe("#e7edf7");
    expect(palette.roles.region).toBe("#ffffff");
    expect(palette.glowIntensity).toBe(0.55);
  });

  it("falls back to the dark values when a token is missing", () => {
    document.documentElement.dataset.theme = "dark";
    const palette = refreshPalette();

    // Nothing is set on the element, so every role comes from the fallback,
    // which is the literal each material was originally built with.
    expect(palette.roles.wall).toBe("#0d1d38");
    expect(palette.roles.pylon).toBe("#0f1a33");
    expect(palette.sky).toBe("#a5b8ff");
    expect(palette.lightIntensity).toBe(1);
  });

  it("reads a theme from the document element, defaulting to dark", () => {
    document.documentElement.removeAttribute("data-theme");
    expect(readEnvPalette().theme).toBe("dark");
  });
});

describe("painting materials", () => {
  it("paints a tagged material for the theme in force", () => {
    useTheme("dark", DARK);
    const wall = themed(new MeshBasicMaterial(), "wall");
    expect(hex(wall)).toBe("#0d1d38");

    const light = useTheme("light", LIGHT);
    paintThemed(wall, light);
    expect(hex(wall)).toBe("#ced9ec");
  });

  it("leaves untagged materials alone, because they encode meaning", () => {
    useTheme("dark", DARK);
    // A CRITICAL severity colour: it means the same thing in both themes.
    const severity = new MeshBasicMaterial({ color: "#ef4444" });

    paintThemed(severity, useTheme("light", LIGHT));

    expect(hex(severity)).toBe("#ef4444");
  });

  it("drops the pylons' self-illumination in daylight", () => {
    useTheme("dark", DARK);
    const pylon = themed(new MeshStandardMaterial(), "pylon");
    expect(`#${pylon.emissive.getHexString()}`).toBe("#12305a");

    paintThemed(pylon, useTheme("light", LIGHT));

    // On a light surface an emissive would simply blow out.
    expect(`#${pylon.emissive.getHexString()}`).toBe("#000000");
    expect(hex(pylon)).toBe("#eef3fb");
  });

  it("survives a layer rebuilding its content", () => {
    // Layers dispose and rebuild their materials on every setModel, so the
    // tag has to live on the material rather than in a registry that would
    // accumulate disposed entries.
    useTheme("dark", DARK);
    const rebuilt = themed(new LineBasicMaterial(), "band");
    expect(rebuilt.userData.themeRole).toBe("band");
    expect(hex(rebuilt)).toBe("#3b5c94");
  });

  it("returns the material so it can be used inline", () => {
    const material = new MeshBasicMaterial();
    expect(themed(material, "wall")).toBe(material);
    expect(themed(null, "wall")).toBeNull();
  });
});

describe("the floor grid", () => {
  // GridHelper bakes its two colours into a vertex-colour attribute, so
  // setting material.color would multiply against them rather than
  // replace them.
  function fakeGrid(divisions) {
    const geometry = new BufferGeometry();
    const vertices = (divisions + 1) * 4;
    geometry.setAttribute("color", new BufferAttribute(new Float32Array(vertices * 3), 3));
    return { geometry, userData: {} };
  }

  function colorAt(grid, line) {
    const attribute = grid.geometry.getAttribute("color");
    const index = line * 4;
    return new Color(attribute.getX(index), attribute.getY(index), attribute.getZ(index));
  }

  it("gives the centre line the major colour and the rest the minor one", () => {
    const palette = useTheme("dark", DARK);
    const grid = fakeGrid(20); // 21 lines, centre at 10
    themedGrid(grid);

    expect(colorAt(grid, 10).getHexString()).toBe(new Color("#1f3a66").getHexString());
    expect(colorAt(grid, 0).getHexString()).toBe(new Color("#132340").getHexString());
    expect(grid.geometry.getAttribute("color").version).toBeGreaterThan(0);
    expect(palette.roles["grid-major"]).toBe("#1f3a66");
  });

  it("repaints for the other theme", () => {
    useTheme("dark", DARK);
    const grid = fakeGrid(20);
    themedGrid(grid);

    paintThemedGrid(grid, useTheme("light", LIGHT));

    expect(colorAt(grid, 10).getHexString()).toBe(new Color("#a8bdda").getHexString());
    expect(colorAt(grid, 0).getHexString()).toBe(new Color("#ccd8ea").getHexString());
  });

  it("ignores objects that are not a tagged grid", () => {
    expect(() => paintThemedGrid(undefined)).not.toThrow();
    expect(() => paintThemedGrid({ userData: {} })).not.toThrow();
    expect(() => paintThemedGrid(fakeGrid(4))).not.toThrow();
  });
});

describe("role lookup", () => {
  it("answers for code that sets a colour directly", () => {
    useTheme("light", LIGHT);
    expect(roleColor("wall-edge")).toBe(LIGHT["--env-wall-edge"]);
  });

  it("returns nothing for a role that does not exist, rather than a wrong colour", () => {
    useTheme("dark", DARK);
    expect(roleColor("not-a-role")).toBeUndefined();
  });
});
