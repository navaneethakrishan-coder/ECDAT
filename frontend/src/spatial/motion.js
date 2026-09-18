// Motion helpers shared by the spatial layer. Every decorative motion
// (parallax, tilt, particles, camera-like transitions) checks these so
// reduced-motion users and touch devices get a still, functional UI.

const queries = {};

function query(text) {
  if (typeof window === "undefined" || !window.matchMedia) return null;
  if (!queries[text]) queries[text] = window.matchMedia(text);
  return queries[text];
}

export function prefersReducedMotion() {
  return Boolean(query("(prefers-reduced-motion: reduce)")?.matches);
}

/** Pointer-driven depth effects: desktop, fine pointer, motion allowed. */
export function allowsPointerDepth() {
  return (
    !prefersReducedMotion() &&
    Boolean(query("(pointer: fine)")?.matches) &&
    Boolean(query("(min-width: 1025px)")?.matches)
  );
}

export function scrollBehavior() {
  return prefersReducedMotion() ? "auto" : "smooth";
}
