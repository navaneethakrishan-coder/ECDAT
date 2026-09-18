import { useSyncExternalStore } from "react";

import { isWebGLAvailable } from "../../components/visualization/mapEnvironment";

const STAGE_QUERY = "(min-width: 601px)";
const DESKTOP_QUERY = "(min-width: 1025px)";

function subscribe(callback) {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const queries = [window.matchMedia(STAGE_QUERY), window.matchMedia(DESKTOP_QUERY)];
  queries.forEach((query) => query.addEventListener("change", callback));
  return () => queries.forEach((query) => query.removeEventListener("change", callback));
}

function snapshot() {
  if (typeof window === "undefined" || !window.matchMedia) return "scroll";
  if (!window.matchMedia(STAGE_QUERY).matches) return "scroll";
  return window.matchMedia(DESKTOP_QUERY).matches ? "desktop" : "tablet";
}

/**
 * Which application layout to use:
 *  - "desktop" (≥1025px) and "tablet" (601–1024px): the shared SpatialStage;
 *  - "scroll": the scrolling layout, for ≤600px, when WebGL is unavailable,
 *    or after the stage's WebGL context was lost.
 */
export function useLayoutMode(contextLost) {
  const width = useSyncExternalStore(subscribe, snapshot, () => "scroll");
  if (width === "scroll" || contextLost || !isWebGLAvailable()) return { mode: "scroll", tier: null };
  return { mode: "stage", tier: width };
}
