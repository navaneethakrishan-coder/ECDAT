/**
 * The 3D environment's colours, read from the same CSS tokens the HTML
 * uses (`--env-*` in theme/theme.css).
 *
 * Keeping one source of truth is the point: the scene follows the theme
 * without a second renderer, a second scene graph, or a JS colour table
 * that can drift from the stylesheet.
 *
 * Only *environment* colours are themed. Severity and strategy colours
 * are deliberately excluded -- they encode meaning, so they must look the
 * same in both themes.
 *
 * A layer tags a material with `themed(material, role)` rather than
 * asking the engine to register it. The tag travels on the material, so
 * it does not matter whether the layer built its content before or after
 * it was attached to the engine -- which is exactly the ordering bug a
 * registry had.
 */

import { Color } from "three";

// Every environment colour in the scene, by role. The dark values are the
// literals these materials were originally constructed with, so naming
// them changed nothing about how dark renders.
const ROLE_TOKENS = {
  "grid-minor": "--env-grid-minor",
  "grid-major": "--env-grid-major",
  wall: "--env-wall",
  "wall-edge": "--env-wall-edge",
  region: "--env-region",
  band: "--env-band",
  plate: "--env-plate",
  track: "--env-track",
  pylon: "--env-pylon",
  column: "--env-column",
  dust: "--env-dust",
};

const FALLBACK = {
  theme: "dark",
  fog: "#05070f",
  fogDensity: 0.016,
  sky: "#a5b8ff",
  ground: "#05070f",
  lightIntensity: 1,
  glowIntensity: 1,
  pylonEmissive: "#12305a",
  roles: {
    "grid-minor": "#132340",
    "grid-major": "#1f3a66",
    wall: "#0d1d38",
    "wall-edge": "#2e4a7a",
    region: "#0f1f3d",
    band: "#3b5c94",
    plate: "#0c1a33",
    track: "#1c2740",
    pylon: "#0f1a33",
    column: "#2e4066",
    dust: "#8fb3e6",
  },
};

function readVar(styles, name, fallback) {
  const value = styles.getPropertyValue(name).trim();
  return value || fallback;
}

function readNumber(styles, name, fallback) {
  const value = parseFloat(styles.getPropertyValue(name));
  return Number.isFinite(value) ? value : fallback;
}

export function readEnvPalette() {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return FALLBACK;
  }

  const styles = getComputedStyle(document.documentElement);
  const roles = {};
  for (const [role, token] of Object.entries(ROLE_TOKENS)) {
    roles[role] = readVar(styles, token, FALLBACK.roles[role]);
  }

  return {
    theme: document.documentElement.dataset.theme === "light" ? "light" : "dark",
    fog: readVar(styles, "--env-fog", FALLBACK.fog),
    fogDensity: readNumber(styles, "--env-fog-density", FALLBACK.fogDensity),
    sky: readVar(styles, "--env-sky", FALLBACK.sky),
    ground: readVar(styles, "--env-ground", FALLBACK.ground),
    lightIntensity: readNumber(styles, "--env-light-intensity", FALLBACK.lightIntensity),
    glowIntensity: readNumber(styles, "--env-glow-intensity", FALLBACK.glowIntensity),
    pylonEmissive: readVar(styles, "--env-pylon-emissive", FALLBACK.pylonEmissive),
    roles,
  };
}

// The palette in force. Layers build materials at all sorts of moments --
// on construction, on attach, on every setModel -- so they read the
// current one rather than being handed it.
let palette = null;

export function currentPalette() {
  if (!palette) palette = readEnvPalette();
  return palette;
}

/** Re-reads the tokens after the theme has changed. */
export function refreshPalette() {
  palette = readEnvPalette();
  return palette;
}

/** The colour for an environment role, for code that sets colours directly. */
export function roleColor(role, active = currentPalette()) {
  return active.roles[role] || FALLBACK.roles[role];
}

/** Paints one already-tagged material for the given palette. */
export function paintThemed(material, active = currentPalette()) {
  const role = material?.userData?.themeRole;
  if (!role || !material.color) return;

  material.color.set(roleColor(role, active));

  // The pylons are the one lit environment material: in the dark console
  // they self-illuminate, which on a white surface would just blow out.
  if (role === "pylon" && material.emissive) {
    material.emissive.set(active.pylonEmissive);
  }
}

/**
 * Tags a material as environment so it follows the theme, and paints it
 * for the current theme now.
 */
export function themed(material, role) {
  if (!material) return material;
  material.userData.themeRole = role;
  paintThemed(material);
  return material;
}

/**
 * Tags a GridHelper for theming.
 *
 * GridHelper bakes its two colours into a vertex-colour attribute rather
 * than the material, so it cannot be repainted by setting material.color
 * -- that would multiply against the baked colours. The tag records the
 * roles; `paintThemedGrid` rewrites the attribute.
 */
export function themedGrid(grid) {
  grid.userData.themeGrid = { major: "grid-major", minor: "grid-minor" };
  paintThemedGrid(grid);
  return grid;
}

/**
 * Rewrites a tagged GridHelper's vertex colours.
 *
 * Mirrors GridHelper's own layout: four vertices per division line, with
 * the centre pair taking the major colour.
 */
export function paintThemedGrid(grid, active = currentPalette()) {
  const roles = grid?.userData?.themeGrid;
  const colors = grid?.geometry?.getAttribute("color");
  if (!roles || !colors) return;

  const major = new Color(roleColor(roles.major, active));
  const minor = new Color(roleColor(roles.minor, active));
  // 4 vertices per division line; GridHelper emits divisions + 1 of them,
  // and gives the major colour to line `divisions / 2` -- which, exactly as
  // in GridHelper, matches nothing when the division count is odd.
  const lines = colors.count / 4;
  const center = (lines - 1) / 2;

  for (let line = 0; line < lines; line += 1) {
    const color = line === center ? major : minor;
    for (let vertex = 0; vertex < 4; vertex += 1) {
      colors.setXYZ(line * 4 + vertex, color.r, color.g, color.b);
    }
  }
  colors.needsUpdate = true;
}
