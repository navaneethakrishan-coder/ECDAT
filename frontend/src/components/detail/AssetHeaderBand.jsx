import { SeverityBadge } from "../Badge";

const SEVERITY_TONE = new Set(["low", "medium", "high", "critical"]);

function toneFor(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return SEVERITY_TONE.has(normalized) ? normalized : "unknown";
}

/**
 * The workspace header band: asset identity on the left, a large "risk
 * hero" readout on the right. Risk is ECDAT's core signal, so instead
 * of burying the severity inside a small badge among six other equal
 * cards, it is rendered here as the single largest, most prominent
 * piece of typography on the page -- exactly once, at the top, where
 * it sets the tone for everything below it.
 */
export function AssetHeaderBand({ assetName, assetDetail }) {
  const category = assetDetail?.classification?.category || "Unclassified";
  const primitive = assetDetail?.inventory?.primitive || assetDetail?.primitive || "Unknown primitive";
  const quantumStatus = assetDetail?.classification?.quantum_status || "unknown";
  const riskReason = assetDetail?.classification?.risk_reason;

  const severity = assetDetail?.current_risk?.severity || "UNKNOWN";
  const score = assetDetail?.current_risk?.score ?? assetDetail?.risk_assessment?.final_score;
  const priorityLevel = assetDetail?.priority?.level || assetDetail?.migration_impact?.priority?.level;

  const tone = toneFor(severity);

  return (
    <section className="workspace-header">
      <div className="workspace-identity">
        <div className={`workspace-avatar workspace-avatar-${tone}`}>
          {assetName.charAt(0).toUpperCase()}
        </div>

        <div className="workspace-identity-text">
          <div className="workspace-eyebrow">{category}</div>
          <h2>{assetName}</h2>
          <div className="workspace-identity-meta">
            <span className="workspace-primitive">{primitive}</span>
            <span
              className={`workspace-quantum-status${
                quantumStatus === "vulnerable" ? " workspace-quantum-vulnerable" : ""
              }`}
            >
              {quantumStatus}
            </span>
          </div>
        </div>
      </div>

      <div className={`workspace-risk-hero risk-hero-${tone}`}>
        <div className="risk-hero-readout">
          <span className="risk-hero-label">Quantum Risk</span>
          <strong className="risk-hero-severity">{severity}</strong>
          {score !== undefined && score !== null && (
            <span className="risk-hero-score">{score} / 100</span>
          )}
        </div>

        {priorityLevel && (
          <div className="risk-hero-priority">
            <span>Migration Priority</span>
            <SeverityBadge value={priorityLevel} />
          </div>
        )}
      </div>

      {riskReason && (
        <p className="workspace-header-reason">
          <SeverityBadge value={severity} fallback="—" /> {riskReason}
        </p>
      )}
    </section>
  );
}
