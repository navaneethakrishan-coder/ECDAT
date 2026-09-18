import { SEVERITIES, SEVERITY_COLORS, STRATEGIES, STRATEGY_META } from "./securityMapModel";

/** Small SVG glyph matching each strategy's 3D/2D node shape. */
export function StrategyGlyph({ strategy, size = 18 }) {
  const c = size / 2;
  const r = size * 0.24;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" className="strategy-glyph">
      {strategy === "KEEP" && (
        <>
          <rect x={c - r} y={c - r} width={r * 2} height={r * 2} rx={1.5} className="glyph-fill" />
          <rect x={c - r - 2.5} y={c - r - 2.5} width={r * 2 + 5} height={r * 2 + 5} rx={2} className="glyph-keep" />
        </>
      )}
      {strategy === "NEEDS_REVIEW" && (
        <>
          <polygon points={`${c},${c - r * 1.3} ${c + r * 1.3},${c} ${c},${c + r * 1.3} ${c - r * 1.3},${c}`} className="glyph-fill" />
          <circle cx={c} cy={c} r={r + 4.5} className="glyph-review" />
        </>
      )}
      {(strategy === "DIRECT_PQC" || strategy === "HYBRID") && (
        <>
          <circle cx={c} cy={c} r={r} className="glyph-fill" />
          <circle cx={c} cy={c} r={r + 3} className="glyph-pqc" />
          {strategy === "HYBRID" && <circle cx={c} cy={c} r={r + 5.8} className="glyph-hybrid" />}
        </>
      )}
    </svg>
  );
}

/**
 * Explains every visual encoding used by the map, so nothing depends on
 * color alone: shape = migration strategy, color = risk severity,
 * size/height = risk score, depth = migration priority.
 */
export function SecurityMapLegend({ open, onToggle, is3d }) {
  return (
    <div className={`security-map-legend${open ? " is-open" : ""}`}>
      <button type="button" className="security-map-legend-toggle" aria-expanded={open} onClick={onToggle}>
        Legend
      </button>

      {open && (
        <div className="security-map-legend-body">
          <div className="legend-group">
            <span className="legend-title">Shape · migration strategy</span>
            <ul>
              {STRATEGIES.map((strategy) => (
                <li key={strategy}>
                  <StrategyGlyph strategy={strategy} />
                  <span>
                    <strong>{STRATEGY_META[strategy].label}</strong> — {STRATEGY_META[strategy].description}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="legend-group">
            <span className="legend-title">Color · risk severity</span>
            <ul className="legend-swatches">
              {SEVERITIES.map((severity) => (
                <li key={severity}>
                  <span className="legend-swatch" style={{ background: SEVERITY_COLORS[severity] }} />
                  {severity}
                </li>
              ))}
            </ul>
          </div>

          <div className="legend-group">
            <span className="legend-title">Position</span>
            <ul className="legend-encodings">
              <li>
                <strong>Region</strong> cryptographic role; key material sits around the algorithm it depends on
              </li>
              <li>
                <strong>{is3d ? "Height · size" : "Height · size"}</strong> risk score (dashed lines: severity thresholds)
              </li>
              <li>
                <strong>{is3d ? "Nearer" : "Lower-right"}</strong> higher migration priority
              </li>
              <li>
                <strong>Arrow</strong> recorded CBOM dependency — impact flows from a finding to what depends on it
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
