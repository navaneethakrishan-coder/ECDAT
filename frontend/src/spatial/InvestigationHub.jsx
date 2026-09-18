import { INVESTIGATION_SURFACES, branchSummaries, severityTone as tone } from "./surfaces";

// Branch anchors in the hub plane. Two compositions share one DOM: a
// tall constellation for the sticky side column and a wide one for the
// band layout used on medium screens (CSS picks which applies).
const COLUMN = {
  view: [360, 420],
  center: [180, 210],
  nodes: {
    evidence: [70, 64],
    risk: [290, 64],
    blast: [62, 210],
    migration: [298, 210],
    whatif: [70, 356],
    ai: [290, 356],
  },
};

const BAND = {
  view: [1000, 230],
  center: [500, 115],
  nodes: {
    evidence: [120, 58],
    risk: [320, 58],
    blast: [220, 172],
    migration: [680, 58],
    whatif: [880, 58],
    ai: [780, 172],
  },
};

function Connectors({ layout, className, activeSurface }) {
  const [width, height] = layout.view;
  const [cx, cy] = layout.center;
  return (
    <svg className={`hub-connectors ${className}`} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      {INVESTIGATION_SURFACES.map((surface) => {
        const [x, y] = layout.nodes[surface.key];
        const midX = (cx + x) / 2;
        return (
          <path
            key={surface.key}
            d={`M ${cx} ${cy} C ${midX} ${cy}, ${midX} ${y}, ${x} ${y}`}
            className={`hub-link${activeSurface === surface.key ? " is-active" : ""}`}
          />
        );
      })}
    </svg>
  );
}

/**
 * The investigation hub: the selected finding at the centre, its
 * analysis surfaces as connected branches. Choosing a branch brings
 * that surface forward in the workspace; the centre returns to the
 * overview. Purely navigational -- every value shown is read from the
 * finding record already loaded for this bom_ref.
 */
export function InvestigationHub({ assetName, assetDetail, activeSurface, inViewSurface, aiStatus, onFocusSurface }) {
  const summaries = branchSummaries(assetDetail, aiStatus);
  const severity = assetDetail?.current_risk?.severity || "UNKNOWN";
  const bomRef = assetDetail?.bom_ref || "";

  return (
    <nav className="investigation-hub" aria-label="Investigation surfaces">
      <div className="hub-stage">
        <div className="hub-plane" data-active={activeSurface || "overview"}>
          <Connectors layout={COLUMN} className="hub-connectors-column" activeSurface={activeSurface} />
          <Connectors layout={BAND} className="hub-connectors-band" activeSurface={activeSurface} />

          <button
            type="button"
            className={`hub-core hub-core-${tone(severity)}${activeSurface ? "" : " is-active"}`}
            style={{
              "--col-x": `${(COLUMN.center[0] / COLUMN.view[0]) * 100}%`,
              "--col-y": `${(COLUMN.center[1] / COLUMN.view[1]) * 100}%`,
              "--band-x": `${(BAND.center[0] / BAND.view[0]) * 100}%`,
              "--band-y": `${(BAND.center[1] / BAND.view[1]) * 100}%`,
            }}
            onClick={() => onFocusSurface(null)}
            aria-pressed={!activeSurface}
            title="Show every analysis surface"
          >
            <span className="hub-core-ring" aria-hidden="true" />
            <span className="hub-core-eyebrow">Finding</span>
            <strong>{assetName}</strong>
            <span className="hub-core-meta">{severity} risk</span>
            <code title={bomRef}>{bomRef ? `${bomRef.slice(0, 8)}…` : ""}</code>
          </button>

          {INVESTIGATION_SURFACES.map((surface) => {
            const summary = summaries[surface.key];
            const [colX, colY] = COLUMN.nodes[surface.key];
            const [bandX, bandY] = BAND.nodes[surface.key];
            const Icon = surface.icon;
            const isActive = activeSurface === surface.key;
            return (
              <button
                type="button"
                key={surface.key}
                className={`hub-branch hub-tone-${summary.tone}${isActive ? " is-active" : ""}${
                  inViewSurface === surface.key ? " is-in-view" : ""
                }`}
                style={{
                  "--col-x": `${(colX / COLUMN.view[0]) * 100}%`,
                  "--col-y": `${(colY / COLUMN.view[1]) * 100}%`,
                  "--band-x": `${(bandX / BAND.view[0]) * 100}%`,
                  "--band-y": `${(bandY / BAND.view[1]) * 100}%`,
                }}
                onClick={() => onFocusSurface(isActive ? null : surface.key)}
                aria-pressed={isActive}
                aria-controls={`surface-${surface.key === "whatif" ? "migration" : surface.key}`}
                data-surface={surface.key}
              >
                <span className="hub-branch-head">
                  <Icon size={13} aria-hidden="true" />
                  {surface.label}
                </span>
                <span className="hub-branch-value">{summary.value}</span>
              </button>
            );
          })}
        </div>
      </div>
      <p className="hub-hint">Select a branch to bring its analysis forward. Select the finding to see everything.</p>
    </nav>
  );
}
