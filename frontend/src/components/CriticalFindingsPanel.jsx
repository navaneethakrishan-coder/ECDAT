import { ShieldAlert } from "lucide-react";

import { strategyPqcPath } from "../migrationStrategy";
import { SeverityBadge } from "./Badge";
import { EmptyState } from "./States";

/**
 * Sits beside the repository-analysis panel on the dashboard's first
 * viewport, so "security posture" and "critical findings" are visible
 * together without scrolling. The candidate pool is every HIGH/
 * CRITICAL-risk-severity finding; within that pool, rows are ordered
 * by App.jsx's `criticalFindings` sort, which ranks by migration
 * priority (not risk severity) -- see the comment there for why. Risk
 * score and priority score/level are both shown per row so the
 * ordering is explainable: two findings can share a risk severity yet
 * rank differently here because their priority scores differ.
 *
 * The PQC path follows the finding's purpose-aware migration strategy
 * when present (e.g. "Needs review" for a finding whose evidence
 * leaves its cryptographic role unresolved).
 */
export function CriticalFindingsPanel({ assets, onSelectAsset }) {
  return (
    <section className="workspace-panel critical-findings-panel" aria-labelledby="critical-findings-heading">
      <div className="section-heading">
        <span className="section-eyebrow">Security Posture</span>
        <h2 id="critical-findings-heading">Migrate First</h2>
        <p>The highest-priority assets to act on, ranked by migration priority (quantum risk, blast radius and migration complexity combined).</p>
      </div>

      {assets.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title="No high-severity assets"
          message="Nothing in the current dataset is flagged HIGH or CRITICAL."
        />
      ) : (
        <ol className="critical-findings-list">
          {assets.map((asset, index) => {
            const strategyPath = strategyPqcPath(asset.migrationStrategy, asset.strategyPqcComponent);

            const pqcText = strategyPath
              ? strategyPath.label
                ? `${strategyPath.text} (${strategyPath.label})`
                : strategyPath.text
              : asset.pqcCandidate || "No direct replacement";

            const pqcNone = strategyPath ? strategyPath.none : !asset.pqcCandidate;

            return (
              <li key={asset.key}>
                <button
                  type="button"
                  className={`critical-finding-row critical-finding-${String(
                    asset.riskSeverity || "unknown"
                  ).toLowerCase()}`}
                  onClick={() => onSelectAsset(asset.bomRef)}
                >
                  <span className="critical-finding-rank">{index + 1}</span>
                  <span className="critical-finding-body">
                    <span className="critical-finding-headline">
                      <span className="critical-finding-name">{asset.name}</span>
                      {typeof asset.riskScore === "number" && (
                        <span className="critical-finding-score">{asset.riskScore}</span>
                      )}
                      <SeverityBadge value={asset.riskSeverity} />
                    </span>
                    <span className="critical-finding-meta">
                      PQC →{" "}
                      <span className={`critical-finding-pqc${pqcNone ? " critical-finding-pqc-none" : ""}`}>
                        {pqcText}
                      </span>
                      <span aria-hidden="true">·</span>
                      Priority{" "}
                      {typeof asset.priorityScore === "number" ? `${asset.priorityScore} · ` : ""}
                      {asset.priorityLevel}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
