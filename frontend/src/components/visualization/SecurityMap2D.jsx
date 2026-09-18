import { useEffect, useMemo, useRef } from "react";

import { SEVERITY_COLORS, STRATEGY_META, displayName, nodeRadius } from "./securityMapModel";

const SCALE = 46;
// Vertical (risk) scale, kept close to the horizontal one for readability.
const SCALE_Y = 32;
const DEPTH_SKEW_X = 0.42;
const DEPTH_SKEW_Y = 0.34;
const PADDING = 56;
const BANDS = [30, 60, 80];

function project(position) {
  return {
    x: (position.x + position.z * DEPTH_SKEW_X) * SCALE,
    y: -position.y * SCALE_Y + position.z * DEPTH_SKEW_Y * SCALE,
  };
}

function NodeGlyph({ node, radius, color }) {
  const r = radius;
  switch (node.strategy) {
    case "KEEP":
      return (
        <>
          <rect x={-r} y={-r} width={r * 2} height={r * 2} rx={3} fill={color} />
          <rect x={-r - 3} y={-r - 3} width={r * 2 + 6} height={r * 2 + 6} rx={4} className="map2d-outline-keep" />
        </>
      );
    case "NEEDS_REVIEW":
      return (
        <>
          <polygon points={`0,${-r * 1.25} ${r * 1.25},0 0,${r * 1.25} ${-r * 1.25},0`} fill={color} />
          <circle r={r + 7} className="map2d-ring-review" />
        </>
      );
    case "HYBRID":
      return (
        <>
          <circle r={r} fill={color} />
          <circle r={r + 5} className="map2d-ring-pqc" />
          <circle r={r + 9} className="map2d-ring-hybrid" />
        </>
      );
    case "DIRECT_PQC":
      return (
        <>
          <circle r={r} fill={color} />
          <circle r={r + 5} className="map2d-ring-pqc" />
        </>
      );
    default:
      return <circle r={r} fill={color} />;
  }
}

/**
 * 2D Security Map: an oblique projection of the same layout the 3D map
 * uses (x = role region, height = risk score, depth = migration
 * priority). Used when WebGL is unavailable, and selectable as a view.
 * Same real findings, same recorded dependency edges, same selection.
 */
export function SecurityMap2D({ model, visibleRefs, searchRefs, focusedRef, relatedRefs, onSelect }) {
  const scrollerRef = useRef(null);
  const layout = useMemo(() => {
    const points = new Map();
    model.nodes.forEach((node) => {
      if (node.position) points.set(node.bomRef, project(node.position));
    });
    const xs = [...points.values()].map((point) => point.x);
    const ys = [...points.values()].map((point) => point.y);
    model.regions.forEach((region) => {
      xs.push(region.start * SCALE, region.end * SCALE);
    });
    const minX = Math.min(...xs, 0) - PADDING;
    const maxX = Math.max(...xs, 0) + PADDING;
    const minY = Math.min(...ys, -model.bounds.height * SCALE_Y) - PADDING;
    const maxY = Math.max(...ys, 0) + PADDING + 30;
    return { points, minX, minY, width: maxX - minX, height: maxY - minY };
  }, [model]);

  // The map keeps a readable scale and scrolls horizontally inside the
  // stage; bring the focused finding into view when focus changes.
  useEffect(() => {
    const scroller = scrollerRef.current;
    const point = focusedRef ? layout.points.get(focusedRef) : null;
    const svg = scroller?.querySelector("svg");
    if (!scroller || !point || !svg) return;
    const scale = svg.getBoundingClientRect().height / layout.height;
    const x = (point.x - layout.minX) * scale;
    scroller.scrollTo({ left: Math.max(0, x - scroller.clientWidth / 2), behavior: "smooth" });
  }, [focusedRef, layout]);

  const isVisible = (ref) => !visibleRefs || visibleRefs.has(ref);

  const nodeState = (ref) => {
    if (focusedRef && ref !== focusedRef && !relatedRefs.has(ref)) return "dim";
    if (searchRefs && !searchRefs.has(ref) && ref !== focusedRef) return "dim";
    return "normal";
  };

  return (
    <div className="security-map-2d" ref={scrollerRef}>
      <svg
        viewBox={`${layout.minX} ${layout.minY} ${layout.width} ${layout.height}`}
        role="group"
        aria-label="Two-dimensional cryptographic security map"
        className="security-map-2d-svg"
        style={{ aspectRatio: `${layout.width} / ${layout.height}` }}
      >
        <defs>
          <marker id="map2d-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" className="map2d-arrow-head" />
          </marker>
          <marker id="map2d-arrow-emphasis" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" className="map2d-arrow-head map2d-arrow-head-emphasis" />
          </marker>
        </defs>

        {BANDS.map((band) => {
          const y = -(band / 100) * model.bounds.height * SCALE_Y;
          return (
            <g key={band} className="map2d-band">
              <line x1={layout.minX + 20} x2={layout.minX + layout.width - 20} y1={y} y2={y} />
              <text x={layout.minX + 24} y={y - 5}>
                risk {band}
              </text>
            </g>
          );
        })}

        {model.regions.map((region) => (
          <g key={region.key} className="map2d-region">
            <rect x={region.start * SCALE - 14} y={-8} width={(region.end - region.start) * SCALE + 28} height={16} rx={4} />
            <text x={region.center * SCALE} y={30} textAnchor="middle">
              {region.label}
            </text>
          </g>
        ))}

        {model.edges.map((edge) => {
          if (!isVisible(edge.from) || !isVisible(edge.to)) return null;
          const from = layout.points.get(edge.from);
          const to = layout.points.get(edge.to);
          const target = model.byRef.get(edge.to);
          if (!from || !to || !target) return null;
          const emphasized =
            focusedRef && (edge.from === focusedRef || edge.to === focusedRef || (relatedRefs.has(edge.from) && relatedRefs.has(edge.to)));
          const dx = to.x - from.x;
          const dy = to.y - from.y;
          const length = Math.hypot(dx, dy) || 1;
          const inset = nodeRadius(target.riskScore) * 22 + 12;
          const endX = to.x - (dx / length) * inset;
          const endY = to.y - (dy / length) * inset;
          const controlX = (from.x + endX) / 2;
          const controlY = Math.min(from.y, endY) - 26;
          return (
            <path
              key={edge.key}
              d={`M ${from.x} ${from.y} Q ${controlX} ${controlY} ${endX} ${endY}`}
              className={`map2d-edge${emphasized ? " is-emphasis" : focusedRef ? " is-dim" : ""}`}
              markerEnd={`url(#${emphasized ? "map2d-arrow-emphasis" : "map2d-arrow"})`}
            />
          );
        })}

        {model.nodes.map((node) => {
          const point = layout.points.get(node.bomRef);
          if (!point || !isVisible(node.bomRef)) return null;
          const radius = nodeRadius(node.riskScore) * 22;
          const color = SEVERITY_COLORS[node.riskSeverity] || SEVERITY_COLORS.UNKNOWN;
          const focused = node.bomRef === focusedRef;
          const state = nodeState(node.bomRef);
          const label = `${displayName(node)}, ${node.riskSeverity} risk ${node.riskScore ?? "not recorded"}, priority ${
            node.priorityLevel
          }, ${STRATEGY_META[node.strategy]?.label || "no strategy"}`;
          return (
            <g
              key={node.bomRef}
              data-bom-ref={node.bomRef}
              transform={`translate(${point.x} ${point.y})`}
              className={`map2d-node is-${state}${focused ? " is-focused" : ""}`}
              role="button"
              tabIndex={0}
              aria-label={label}
              aria-pressed={focused}
              onClick={() => onSelect(node.bomRef)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(node.bomRef);
                }
              }}
            >
              <title>{label}</title>
              {focused && <circle r={radius + 16} className="map2d-focus-ring" />}
              <NodeGlyph node={node} radius={radius} color={color} />
              {(focused || ["HIGH", "CRITICAL"].includes(node.priorityLevel)) && (
                <text y={-radius - 16} textAnchor="middle" className="map2d-node-label">
                  {displayName(node)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
