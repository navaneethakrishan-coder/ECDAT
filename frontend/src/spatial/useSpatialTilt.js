import { useCallback, useRef } from "react";

import { allowsPointerDepth } from "./motion";

/**
 * Subtle pointer tilt for a spatial surface (max ±`maxDegrees`), plus a
 * light position for its inner glare. Writes CSS variables only, once
 * per animation frame, and only while a mouse is over the surface --
 * nothing runs when idle. Disabled for touch, reduced motion and
 * narrow viewports (see allowsPointerDepth).
 */
export function useSpatialTilt(maxDegrees = 2.5) {
  const frame = useRef(0);
  const pending = useRef(null);

  const apply = useCallback((element) => {
    frame.current = 0;
    const point = pending.current;
    if (!element || !point) return;
    element.style.setProperty("--tilt-x", `${(-(point.y - 0.5) * 2 * maxDegrees).toFixed(2)}deg`);
    element.style.setProperty("--tilt-y", `${((point.x - 0.5) * 2 * maxDegrees).toFixed(2)}deg`);
    element.style.setProperty("--glare-x", `${(point.x * 100).toFixed(1)}%`);
    element.style.setProperty("--glare-y", `${(point.y * 100).toFixed(1)}%`);
  }, [maxDegrees]);

  const onPointerMove = useCallback(
    (event) => {
      if (event.pointerType !== "mouse" || !allowsPointerDepth()) return;
      const element = event.currentTarget;
      const rect = element.getBoundingClientRect();
      pending.current = {
        x: Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1),
        y: Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1),
      };
      element.dataset.tilting = "true";
      if (!frame.current) frame.current = requestAnimationFrame(() => apply(element));
    },
    [apply],
  );

  const onPointerLeave = useCallback((event) => {
    const element = event.currentTarget;
    if (frame.current) cancelAnimationFrame(frame.current);
    frame.current = 0;
    pending.current = null;
    delete element.dataset.tilting;
    element.style.removeProperty("--tilt-x");
    element.style.removeProperty("--tilt-y");
    element.style.removeProperty("--glare-x");
    element.style.removeProperty("--glare-y");
  }, []);

  return { onPointerMove, onPointerLeave };
}
