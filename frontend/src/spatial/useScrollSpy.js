import { useEffect, useState } from "react";

/**
 * Which of the given page regions is currently in the reading band of
 * the viewport (or of `root`). `targets` is a stable array of
 * { key, selector }. Uses one IntersectionObserver; no scroll handlers.
 */
export function useScrollSpy(targets, { root = null, enabled = true, rootMargin = "-30% 0px -60% 0px" } = {}) {
  const [active, setActive] = useState(null);

  useEffect(() => {
    if (!enabled || typeof IntersectionObserver === "undefined") return undefined;
    const scope = root || document;
    const elements = targets
      .map((target) => ({ key: target.key, element: scope.querySelector(target.selector) }))
      .filter((entry) => entry.element);
    if (!elements.length) return undefined;

    const visible = new Set();
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const match = elements.find((item) => item.element === entry.target);
          if (!match) return;
          if (entry.isIntersecting) visible.add(match.key);
          else visible.delete(match.key);
        });
        // Document order decides ties: the last region whose top has
        // entered the reading band is the one being read.
        const current = [...elements].reverse().find((item) => visible.has(item.key));
        if (current) setActive(current.key);
      },
      { root, rootMargin, threshold: 0 },
    );

    elements.forEach((item) => observer.observe(item.element));
    return () => observer.disconnect();
  }, [targets, root, enabled, rootMargin]);

  return active;
}
