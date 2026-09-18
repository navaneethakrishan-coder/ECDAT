import { ArrowDown, ArrowUpRight, Binary, GitCompareArrows, ShieldAlert, ShieldCheck } from "lucide-react";

import { strategyPqcPath } from "../../migrationStrategy";
import { MigrationTransition } from "./MigrationTransition";
import { WhatIfSimulator } from "./WhatIfSimulator";

const SEVERITY_TONE = new Set(["low", "medium", "high", "critical"]);

function toneFor(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return SEVERITY_TONE.has(normalized) ? normalized : "unknown";
}

// The backend's eight explanation questions, in the order a reviewer
// reads them (see backend/services/migration_strategy.py).
const EXPLANATION_LABELS = [
  ["detected", "What was detected"],
  ["resolved_purpose", "Resolved purpose"],
  ["purpose_evidence", "Purpose evidence"],
  ["classification_confidence", "Classification confidence"],
  ["quantum_relevance", "Why it is quantum-relevant"],
  ["pqc_selection", "PQC selection"],
  ["strategy_rationale", "Why this strategy"],
  ["expected_impact", "Expected migration impact"],
];

/**
 * Purpose-aware migration strategy: the decision, its components and
 * the evidence behind it. Everything shown is read from
 * assetDetail.migration_strategy; nothing is inferred here.
 */
function MigrationStrategy({ strategy }) {
  const explanation = strategy.explanation || {};
  const factors = strategy.decision_factors || [];
  const options = strategy.review_options || [];

  return (
    <div className={`migration-strategy migration-strategy-${String(strategy.strategy).toLowerCase()}`}>
      <div className="migration-strategy-head">
        <span>Migration Strategy</span>
        <strong>{strategy.label || strategy.strategy}</strong>
        <span className="badge badge-tag">Confidence {strategy.confidence || "UNKNOWN"}</span>
      </div>

      <dl className="migration-strategy-grid">
        <div>
          <dt>Current</dt>
          <dd>{strategy.current_algorithm}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{strategy.purpose_class_label}</dd>
        </div>
        {strategy.classical_component && (
          <div>
            <dt>Classical component</dt>
            <dd>{strategy.classical_component}</dd>
          </div>
        )}
        {strategy.pqc_component && (
          <div>
            <dt>PQC component</dt>
            <dd className="migration-strategy-pqc">{strategy.pqc_component}</dd>
          </div>
        )}
      </dl>

      <p className="migration-strategy-why">
        <strong>Why —</strong> {strategy.rationale}
      </p>

      {strategy.construction && <p className="migration-strategy-construction">{strategy.construction}</p>}

      <details className="workspace-disclosure">
        <summary>View decision evidence</summary>
        <div className="migration-strategy-evidence">
          <dl>
            {EXPLANATION_LABELS.filter(([key]) => explanation[key]).map(([key, label]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>{explanation[key]}</dd>
              </div>
            ))}
          </dl>

          {factors.length > 0 && (
            <ul className="migration-strategy-factors">
              {factors.map((factor) => (
                <li key={factor.signal}>
                  <strong>{factor.signal.replaceAll("_", " ")}</strong>: {factor.value ?? "unknown"} — {factor.effect}
                </li>
              ))}
            </ul>
          )}

          {options.length > 0 && (
            <ul className="migration-strategy-factors">
              {options.map((option) => (
                <li key={option.purpose_class}>
                  If the usage is <strong>{option.purpose_class_label}</strong>: evaluate{" "}
                  {option.top_candidate || "no available candidate"} ({option.pqc_family || "no PQC family"})
                </li>
              ))}
            </ul>
          )}
        </div>
      </details>
    </div>
  );
}

/**
 * The migration recommendation as a vertical decision pathway: what
 * exists today, the quantum risk that creates, the PQC component the
 * migration strategy selected, and the first concrete developer step
 * -- four connected nodes read top to bottom in seconds. The strategy
 * and its evidence follow, and ranked alternatives and the full action
 * list stay behind progressive disclosure.
 */
export function MigrationFlow({ assetDetail }) {
  const primitive = assetDetail?.inventory?.primitive || assetDetail?.primitive || "Current algorithm";
  const severity = assetDetail?.current_risk?.severity || "UNKNOWN";
  const recommendation = assetDetail?.recommendation || {};
  const pqcMigration = assetDetail?.pqc_migration || {};
  const actions = assetDetail?.migration_actions || [];
  const rankedCandidates = assetDetail?.ranked_candidates || [];
  const strategy = assetDetail?.migration_strategy || null;

  const strategyPath = strategyPqcPath(strategy?.strategy, strategy?.pqc_component);
  const pqcText = strategyPath ? strategyPath.text : recommendation.candidate || "No direct replacement";
  const pqcNone = strategyPath ? strategyPath.none : !recommendation.candidate;

  // Ranking-model output, labelled as such and kept apart from the
  // migration decision: only the strategy selects a PQC component.
  const topRanked = rankedCandidates[0] || null;
  const rankingStatus = !topRanked || !strategy
    ? "unlabelled"
    : strategy.strategy === "NEEDS_REVIEW"
    ? "not-selected-review"
    : topRanked.candidate === strategy.pqc_component
    ? "selected"
    : "not-selected";

  const firstAction = actions[0]?.action;
  const remainingActions = actions.slice(1);

  const riskTone = toneFor(severity);

  return (
    <section className="workspace-panel panel-migration" aria-labelledby="migration-flow-heading">
      <h3 id="migration-flow-heading">
        <GitCompareArrows size={15} aria-hidden="true" />
        Migration Path
      </h3>

      <MigrationTransition strategy={strategy} topRanked={topRanked} />

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

        <div className={`flow-node flow-node-pqc${pqcNone ? " flow-node-pqc-none" : ""}`}>
          <ShieldCheck size={16} className="flow-node-icon" aria-hidden="true" />
          <span>
            {strategyPath?.label
              ? `PQC Component · ${strategyPath.label}`
              : strategy
              ? "Migration Decision"
              : "PQC Candidate"}
          </span>
          <strong>{pqcText}</strong>
        </div>

        <ArrowDown className="flow-arrow" size={16} aria-hidden="true" />

        <div className="flow-node flow-node-action">
          <ArrowUpRight size={16} className="flow-node-icon" aria-hidden="true" />
          <span>Migration Action</span>
          <strong>{firstAction || "No action generated"}</strong>
        </div>
      </div>

      {strategy && <MigrationStrategy strategy={strategy} />}

      {assetDetail?.bom_ref && <WhatIfSimulator key={assetDetail.bom_ref} bomRef={assetDetail.bom_ref} />}

      <div className="migration-meta-row">
        <span>
          Migration type: <strong>{pqcMigration.migration_type || "N/A"}</strong>
        </span>
        <span>
          Mapping confidence: <strong>{pqcMigration.confidence || "N/A"}</strong>
        </span>
        {topRanked && (
          <span className="migration-ranking-note" data-ranking-status={rankingStatus}>
            Ranking-model candidate: <strong>{topRanked.candidate}</strong> (#{topRanked.rank ?? 1} of{" "}
            {rankedCandidates.length})
            {rankingStatus === "selected" && <em> — selected by the migration strategy</em>}
            {rankingStatus === "not-selected-review" && <em> — not selected: migration requires review</em>}
            {rankingStatus === "not-selected" && <em> — not selected by the migration strategy</em>}
          </span>
        )}
      </div>

      {rankedCandidates.length > 1 && (
        <details className="workspace-disclosure">
          <summary>
            {strategy?.strategy === "NEEDS_REVIEW"
              ? `View ${rankedCandidates.length} ranking-model candidates (none selected)`
              : `View ${rankedCandidates.length} ranked alternatives`}
          </summary>
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
