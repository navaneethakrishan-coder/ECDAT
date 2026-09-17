import { migrationDecisionDisplay } from "../../migrationStrategy";
import { SeverityBadge } from "../Badge";

const SEVERITY_TONE = new Set(["low", "medium", "high", "critical"]);

function toneFor(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return SEVERITY_TONE.has(normalized) ? normalized : "unknown";
}

/**
 * The workspace header band: asset identity on the left, then the
 * three facts an evaluator needs before anything else -- the risk
 * score (the single largest number on the page, severity-colored),
 * migration priority, and the recommended PQC replacement. Everything
 * in the workspace below elaborates on these; nothing repeats them at
 * the same visual weight.
 */
export function AssetHeaderBand({ assetName, assetDetail }) {
  const category = assetDetail?.classification?.category || "Unclassified";
  const primitive = assetDetail?.inventory?.primitive || assetDetail?.primitive || "Unknown primitive";
  const quantumStatus = assetDetail?.classification?.quantum_status || "unknown";
  const riskReason = assetDetail?.classification?.risk_reason;

  const severity = assetDetail?.current_risk?.severity || "UNKNOWN";
  const rawScore = assetDetail?.current_risk?.score ?? assetDetail?.risk_assessment?.final_score;
  const hasScore = typeof rawScore === "number";
  const priorityLevel = assetDetail?.priority?.level || assetDetail?.migration_impact?.priority?.level;
  // The headline migration fact comes from the authoritative migration
  // strategy, never from the ranking model's top candidate alone (a
  // NEEDS_REVIEW finding still has ranking output, but no recommendation).
  const strategy = assetDetail?.migration_strategy;
  const decision = migrationDecisionDisplay(strategy?.strategy, strategy?.pqc_component) || {
    // Legacy dataset without strategies.
    label: "PQC Recommendation",
    text: assetDetail?.recommendation?.candidate || "No direct replacement",
    state: assetDetail?.recommendation?.candidate ? "selected" : "none",
  };

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
          <div className="risk-hero-value">
            {hasScore && <strong className="risk-hero-number">{rawScore}</strong>}
            <div className="risk-hero-value-meta">
              <span className={`risk-hero-severity${hasScore ? "" : " risk-hero-severity-solo"}`}>{severity}</span>
              {hasScore && <span className="risk-hero-score">/ 100</span>}
            </div>
          </div>
        </div>

        {priorityLevel && (
          <div className="risk-hero-fact">
            <span>Migration Priority</span>
            <SeverityBadge value={priorityLevel} />
          </div>
        )}

        <div className="risk-hero-fact" data-decision-state={decision.state}>
          <span>{decision.label}</span>
          <strong
            className={`risk-hero-pqc${
              decision.state === "unresolved"
                ? " risk-hero-pqc-review"
                : decision.state === "none"
                ? " risk-hero-pqc-none"
                : ""
            }`}
          >
            {decision.text}
          </strong>
        </div>
      </div>

      {riskReason && (
        <p className="workspace-header-reason">
          <SeverityBadge value={severity} fallback="—" /> {riskReason}
        </p>
      )}
    </section>
  );
}
