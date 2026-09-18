import { memo, useEffect, useMemo, useRef } from "react";

import { allowsPointerDepth } from "./motion";

// Deterministic pseudo-random layout so the environment is identical on
// every load (no flicker, no layout drift between renders).
function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const WIDTH = 1600;
const HEIGHT = 1000;

function buildNetwork() {
  const random = seeded(20260917);
  const nodes = Array.from({ length: 28 }, () => ({
    x: 40 + random() * (WIDTH - 80),
    y: 30 + random() * (HEIGHT * 0.62),
    r: 1 + random() * 1.6,
  }));
  const links = new Set();
  nodes.forEach((node, index) => {
    nodes
      .map((other, otherIndex) => ({ otherIndex, d: Math.hypot(other.x - node.x, other.y - node.y) }))
      .filter((item) => item.otherIndex !== index)
      .sort((a, b) => a.d - b.d)
      .slice(0, 2)
      .forEach(({ otherIndex, d }) => {
        if (d < 360) links.add([Math.min(index, otherIndex), Math.max(index, otherIndex)].join("-"));
      });
  });
  const particles = [0, 1, 2].map((layer) =>
    Array.from({ length: 22 }, () => ({
      x: random() * WIDTH,
      y: random() * HEIGHT,
      r: 0.6 + random() * (0.6 + layer * 0.5),
    })),
  );
  return {
    nodes,
    links: [...links].map((key) => key.split("-").map(Number)),
    particles,
  };
}

/**
 * The global spatial environment behind every ECDAT screen: a
 * perspective floor grid, faint structural planes, a static security
 * network and three depth layers of particles. It is decorative only
 * (aria-hidden), low-contrast, and does not animate on its own.
 *
 * Depth comes from two inputs:
 *  - `mode` (global / map / finding / investigation / simulation) slowly
 *    re-stages the environment with CSS transitions when the user's
 *    context changes;
 *  - pointer parallax (desktop, fine pointer, motion allowed): each
 *    layer shifts by 2–8px, written once per frame only while the
 *    pointer moves.
 */
export const SpatialEnvironment = memo(function SpatialEnvironment({ mode = "global" }) {
  const rootRef = useRef(null);
  const network = useMemo(() => buildNetwork(), []);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    let frame = 0;
    let point = null;

    function apply() {
      frame = 0;
      if (!point) return;
      root.style.setProperty("--px", point.x.toFixed(3));
      root.style.setProperty("--py", point.y.toFixed(3));
    }

    function handleMove(event) {
      if (event.pointerType !== "mouse" || !allowsPointerDepth()) return;
      point = {
        x: (event.clientX / window.innerWidth) * 2 - 1,
        y: (event.clientY / window.innerHeight) * 2 - 1,
      };
      if (!frame) frame = requestAnimationFrame(apply);
    }

    window.addEventListener("pointermove", handleMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", handleMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div ref={rootRef} className="spatial-environment" data-mode={mode} aria-hidden="true">
      <div className="space-layer-far">
        <div className="space-plane space-plane-left" />
        <div className="space-plane space-plane-right" />
      </div>

      <div className="space-layer-mid">
        <svg className="space-network" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="xMidYMid slice">
          {network.links.map(([a, b]) => (
            <line
              key={`${a}-${b}`}
              x1={network.nodes[a].x}
              y1={network.nodes[a].y}
              x2={network.nodes[b].x}
              y2={network.nodes[b].y}
            />
          ))}
          {network.nodes.map((node, index) => (
            <circle key={index} cx={node.x} cy={node.y} r={node.r} />
          ))}
        </svg>
      </div>

      <div className="space-floor-wrap">
        <div className="space-floor" />
      </div>

      {network.particles.map((layer, depth) => (
        <svg
          key={depth}
          className={`space-particles space-particles-${depth}`}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="xMidYMid slice"
        >
          {layer.map((particle, index) => (
            <circle key={index} cx={particle.x} cy={particle.y} r={particle.r} />
          ))}
        </svg>
      ))}

      <div className="space-vignette" />
    </div>
  );
});
