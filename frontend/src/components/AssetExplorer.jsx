import { Database } from "lucide-react";

import { SeverityBadge } from "./Badge";
import { EmptyState } from "./States";

/**
 * Each row reads as a security finding, not a plain data row: risk
 * and migration priority are the dominant, largest-type elements
 * (left rail + primary badges); complexity/blast-radius/source-impact
 * are demoted to a single quiet meta line so they support the
 * finding instead of competing with it for attention. HIGH/CRITICAL
 * rows get a tinted background so they visually stand out while
 * scanning the list, without any animation or neon treatment.
 *
 * Data comes from two already-existing bulk endpoints joined by asset
 * name -- GET /api/migration-report/assets (risk/PQC/source-impact)
 * and GET /api/priority (priority/complexity/blast-radius) -- both
 * already fetched once on load, nothing new added for this view.
 */
export function AssetExplorer({ assets, totalCount, selectedAsset, onSelectAsset }) {
  return (
    <div className="asset-explorer-list" role="list">
      {assets.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No assets found"
          message="Try a different search term or clear the active filters."
        />
      ) : (
        assets.map((asset, index) => {
          const isSelected = selectedAsset === asset.name;
          const severity = String(asset.riskSeverity || "unknown").toLowerCase();

          return (
            <button
              type="button"
              role="listitem"
              key={`${asset.key}-${index}`}
              className={`asset-card risk-accent-${severity}${isSelected ? " asset-card-selected" : ""}`}
              onClick={() => onSelectAsset(asset.name)}
              aria-current={isSelected ? "true" : undefined}
            >
              <div className={`asset-card-severity-rail severity-rail-${severity}`} aria-hidden="true" />

              <div className="asset-card-identity">
                <span className="asset-card-name">{asset.name}</span>
                <span className="asset-card-meta">
                  {asset.type} · {asset.primitive}
                </span>
              </div>

              <div className="asset-card-primary-metrics">
                <div className="asset-card-metric asset-card-metric-primary">
                  <span>Risk</span>
                  <SeverityBadge value={asset.riskSeverity} />
                </div>
                <div className="asset-card-metric asset-card-metric-primary">
                  <span>Priority</span>
                  <SeverityBadge value={asset.priorityLevel} />
                </div>
                <div className="asset-card-metric-pqc">
                  <span>PQC Recommendation</span>
                  <strong>{asset.pqcCandidate || "No direct replacement"}</strong>
                </div>
              </div>

              <div className="asset-card-secondary-meta">
                <span>Complexity {asset.complexityLevel}</span>
                <span aria-hidden="true">·</span>
                <span>Blast {asset.blastSeverity}</span>
                <span aria-hidden="true">·</span>
                <span>Impact {asset.sourceImpact}</span>
              </div>
            </button>
          );
        })
      )}

      {assets.length > 0 && (
        <div className="asset-explorer-footnote">
          Showing {assets.length} of {totalCount} analyzed cryptographic assets.
        </div>
      )}
    </div>
  );
}
