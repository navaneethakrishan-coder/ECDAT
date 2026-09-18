const SIZE = 148;
const CENTER = SIZE / 2;
const VALUE_RADIUS = 60;
const DEPTH_RADIUS = 70;

const SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SEVERITY_COLORS = {
  CRITICAL: "var(--sev-critical)",
  HIGH: "var(--sev-high)",
  MEDIUM: "var(--sev-medium)",
  LOW: "var(--sev-low)",
};

function polar(radius, fraction) {
  const angle = fraction * Math.PI * 2 - Math.PI / 2;
  return { x: CENTER + radius * Math.cos(angle), y: CENTER + radius * Math.sin(angle) };
}

function arcPath(radius, from, to) {
  const span = Math.min(Math.max(to - from, 0), 0.9999);
  const start = polar(radius, from);
  const end = polar(radius, from + span);
  return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${radius} ${radius} 0 ${span > 0.5 ? 1 : 0} 1 ${end.x.toFixed(
    2,
  )} ${end.y.toFixed(2)}`;
}

/**
 * Quantum readiness as a layered posture instrument. Front layer: the
 * readiness arc (the headline number, unchanged). Depth layer, tilted
 * behind it: the real risk-severity distribution from /api/summary as
 * ring segments. Two particles travel the readiness arc a few times on
 * load and then stop; nothing loops forever.
 */
export function ReadinessCore({ percent, tone, distribution = {}, label }) {
  const total = SEVERITY_ORDER.reduce((sum, key) => sum + (distribution[key] || 0), 0);
  const valueFraction = Math.min(Math.max(percent / 100, 0), 1);

  let cursor = 0;
  const segments = total
    ? SEVERITY_ORDER.filter((key) => distribution[key]).map((key) => {
        const share = distribution[key] / total;
        const gap = 0.012;
        const segment = { key, path: arcPath(DEPTH_RADIUS, cursor + gap / 2, cursor + share - gap / 2) };
        cursor += share;
        return segment;
      })
    : [];

  const valuePath = arcPath(VALUE_RADIUS, 0, valueFraction);
  const summary = SEVERITY_ORDER.map((key) => `${distribution[key] || 0} ${key.toLowerCase()}`).join(", ");

  return (
    <div
      className={`readiness-core readiness-core-${tone}`}
      role="img"
      aria-label={`${label}: ${percent}% ready. Risk severity across findings: ${summary}.`}
      style={{ "--readiness-path": `path("${valuePath}")` }}
    >
      <div className="readiness-core-depth" aria-hidden="true">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`}>
          <circle cx={CENTER} cy={CENTER} r={DEPTH_RADIUS + 8} className="readiness-core-orbit" />
          {segments.map((segment) => (
            <path key={segment.key} d={segment.path} style={{ stroke: SEVERITY_COLORS[segment.key] }} className="readiness-core-segment" />
          ))}
        </svg>
      </div>

      <svg className="readiness-core-front" viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true">
        <circle cx={CENTER} cy={CENTER} r={VALUE_RADIUS} className="readiness-core-track" />
        {valueFraction > 0 && <path d={valuePath} className="readiness-core-value" />}
        <circle cx={CENTER} cy={CENTER} r={VALUE_RADIUS - 13} className="readiness-core-inner" />
      </svg>

      {valueFraction > 0.04 && (
        <>
          <span className="readiness-core-particle" aria-hidden="true" />
          <span className="readiness-core-particle readiness-core-particle-late" aria-hidden="true" />
        </>
      )}

      <div className="readiness-core-number">
        <strong>{percent}%</strong>
        <span>ready</span>
      </div>
    </div>
  );
}
