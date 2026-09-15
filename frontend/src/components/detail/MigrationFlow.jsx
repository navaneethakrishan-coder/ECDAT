import { ArrowDown, ArrowUpRight, Binary, GitCompareArrows, ShieldAlert, ShieldCheck } from "lucide-react";

const SEVERITY_TONE = new Set(["low", "medium", "high", "critical"]);

function toneFor(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return SEVERITY_TONE.has(normalized) ? normalized : "unknown";
}

/**
 * The migration recommendation as a vertical decision pathway: what
 * exists today, the quantum risk that creates, the PQC candidate ECDAT
 * ranked highest, and the first concrete developer step -- four
 * connected nodes read top to bottom in seconds. Ranked alternatives
 * and the full action list stay behind progressive disclosure instead
 * of taking up permanent space.
 */
export function MigrationFlow({ assetDetail }) {
  const primitive = assetDetail?.inventory?.primitive || assetDetail?.primitive || "Current algorithm";
  const severity = assetDetail?.current_risk?.severity || "UNKNOWN";
  const recommendation = assetDetail?.recommendation || {};
  const pqcMigration = assetDetail?.pqc_migration || {};
  const actions = assetDetail?.migration_actions || [];
  const rankedCandidates = assetDetail?.ranked_candidates || [];

  const firstAction = actions[0]?.action;
  const remainingActions = actions.slice(1);

  const riskTone = toneFor(severity);

  return (
    <section className="workspace-panel panel-migration" aria-labelledby="migration-flow-heading">
      <h3 id="migration-flow-heading">
        <GitCompareArrows size={15} aria-hidden="true" />
        Migration Path
      </h3>

      <div className="migration-flow">
        <div className="flow-node flow-node-current">
          <Binary size={16} className="flow-node-icon" aria-hidden="true" />
          <span>Current Cryptography</span>
          <strong>{primitive}</strong>
        </div>

        <ArrowDown className="flow-arrow" size={16} aria-hidden="true" />

        <div className={`flow-node flow-node-risk flow-node-${riskTone}`}>
          <ShieldAlert size={16} className="flow-node-icon" aria-hidden="true" />
          <span>Quantum Risk</span>
          <strong>{severity}</strong>
        </div>

        <ArrowDown className="flow-arrow" size={16} aria-hidden="true" />

        <div className={`flow-node flow-node-pqc${recommendation.candidate ? "" : " flow-node-pqc-none"}`}>
          <ShieldCheck size={16} className="flow-node-icon" aria-hidden="true" />
          <span>PQC Candidate</span>
          <strong>{recommendation.candidate || "No direct replacement"}</strong>
        </div>

        <ArrowDown className="flow-arrow" size={16} aria-hidden="true" />

        <div className="flow-node flow-node-action">
          <ArrowUpRight size={16} className="flow-node-icon" aria-hidden="true" />
          <span>Migration Action</span>
          <strong>{firstAction || "No action generated"}</strong>
        </div>
      </div>

      <div className="migration-meta-row">
        <span>
          Migration type: <strong>{pqcMigration.migration_type || "N/A"}</strong>
        </span>
        <span>
          Confidence: <strong>{pqcMigration.confidence || "N/A"}</strong>
        </span>
        {recommendation.candidate_rank && (
          <span>
            Rank: <strong>#{recommendation.candidate_rank}</strong> of {rankedCandidates.length || "—"}
          </span>
        )}
      </div>

      {rankedCandidates.length > 1 && (
        <details className="workspace-disclosure">
          <summary>View {rankedCandidates.length} ranked alternatives</summary>
          <div className="candidate-ranking-list">
            {rankedCandidates.map((candidate, index) => (
              <div
                className="candidate-ranking-row"
                key={`${candidate.candidate || candidate.name || "candidate"}-${index}`}
              >
                <div className="candidate-rank">#{candidate.rank || index + 1}</div>
                <div className="candidate-info">
                  <strong>{candidate.candidate || candidate.name || "Unknown"}</strong>
                  <span>{candidate.family || "PQC candidate"}</span>
                </div>
                <div className="candidate-score">
                  <strong>{candidate.score ?? "—"}</strong>
                  <span>Score</span>
                </div>
              </div>
            ))}
          </div>
        </details>
      )}

      {remainingActions.length > 0 && (
        <details className="workspace-disclosure">
          <summary>View all {actions.length} migration actions</summary>
          <div className="action-list">
            {actions.map((action, index) => (
              <div className="migration-action" key={`${action.step ?? index}-${index}`}>
                <div className="action-number">{action.step || index + 1}</div>
                <span>{action.action}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {actions.length === 0 && (
        <p className="workspace-empty-note">No migration actions were generated for this asset.</p>
      )}
    </section>
  );
}
