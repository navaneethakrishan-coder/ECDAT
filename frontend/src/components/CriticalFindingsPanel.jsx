import { ShieldAlert } from "lucide-react";

import { SeverityBadge } from "./Badge";
import { EmptyState } from "./States";

/**
 * Sits beside the repository-analysis panel on the dashboard's first
 * viewport, so "security posture" and "critical findings" are visible
 * together without scrolling. Ranked purely by the same severity
 * ordinal every other severity badge already uses (CRITICAL > HIGH >
 * MEDIUM > LOW) -- no new score is invented, this is a client-side
 * sort of data the Asset Explorer already has.
 */
export function CriticalFindingsPanel({ assets, onSelectAsset }) {
  return (
    <section className="workspace-panel critical-findings-panel" aria-labelledby="critical-findings-heading">
      <div className="section-heading">
        <span className="section-eyebrow">Security Posture</span>
        <h2 id="critical-findings-heading">Migrate First</h2>
        <p>The highest-priority assets to act on, ranked by quantum risk.</p>
      </div>

      {assets.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title="No high-severity assets"
          message="Nothing in the current dataset is flagged HIGH or CRITICAL."
        />
      ) : (
        <ol className="critical-findings-list">
          {assets.map((asset, index) => (
            <li key={asset.key}>
              <button
                type="button"
                className={`critical-finding-row critical-finding-${String(
                  asset.riskSeverity || "unknown"
                ).toLowerCase()}`}
                onClick={() => onSelectAsset(asset.name)}
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
                    <span className={`critical-finding-pqc${asset.pqcCandidate ? "" : " critical-finding-pqc-none"}`}>
                      {asset.pqcCandidate || "No direct replacement"}
                    </span>
                    <span aria-hidden="true">·</span>
                    Priority {asset.priorityLevel}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
