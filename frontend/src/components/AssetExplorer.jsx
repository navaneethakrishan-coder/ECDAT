import { ArrowRight, Database } from "lucide-react";

import { SeverityBadge } from "./Badge";
import { EmptyState } from "./States";

// Same wording AssetFilters.jsx already uses for these slugs -- kept
// here too so a card's "PQC Path" line reads in plain language
// instead of the raw backend slug.
const MIGRATION_TYPE_LABELS = {
  "pqc-candidate": "PQC Candidate",
  "architectural-migration": "Architectural Migration",
  "no-direct-pqc-replacement": "No Direct Replacement",
  "not-applicable": "Not Applicable",
};

/**
 * Each card reads as a security finding, not a plain data row: risk
 * (severity + numeric score) is the dominant, largest-type element,
 * with migration priority right beside it. A short identity line and
 * the PQC migration path follow; complexity/blast-radius/source-impact
 * are demoted to one quiet meta line so they support the finding
 * instead of competing with it for attention. HIGH/CRITICAL rows get
 * a tinted background so they visually stand out while scanning the
 * list, without any animation or neon treatment.
 *
 * Data comes from two already-existing bulk endpoints joined by CBOM
 * bom-ref -- GET /api/migration-report/assets (risk/PQC/source-impact)
 * and GET /api/priority (priority/complexity/blast-radius) -- both
 * already fetched once on load, nothing new added for this view. A
 * per-asset source file/line is intentionally NOT shown here: the
 * bulk endpoints don't return it, only GET /api/asset/{name} does
 * (one call per row would mean 29 extra requests just to populate a
 * list) -- exact evidence lives one click away, in Asset Detail's
 * Source & Evidence panel, where that call already happens once.
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
          const isSelected = selectedAsset === asset.bomRef;
          const severity = String(asset.riskSeverity || "unknown").toLowerCase();
          const migrationPath = MIGRATION_TYPE_LABELS[asset.migrationType] || "Not yet classified";

          return (
            <button
              type="button"
              role="listitem"
              key={`${asset.key}-${index}`}
              className={`asset-card risk-accent-${severity}${isSelected ? " asset-card-selected" : ""}`}
              onClick={() => onSelectAsset(asset.bomRef)}
              aria-current={isSelected ? "true" : undefined}
            >
              <div className={`asset-card-severity-rail severity-rail-${severity}`} aria-hidden="true" />

              <div className="asset-card-main">
                <div className="asset-card-headline">
                  <div className="asset-card-headline-left">
                    <SeverityBadge value={asset.riskSeverity} />
                    <span className="asset-card-name">{asset.name}</span>
                  </div>

                  <div className="asset-card-headline-right">
                    {typeof asset.riskScore === "number" && (
                      <span className="asset-card-score">{asset.riskScore}</span>
                    )}
                    <div className="asset-card-metric-primary">
                      <span>Priority</span>
                      <SeverityBadge value={asset.priorityLevel} />
                    </div>
                  </div>
                </div>

                <div className="asset-card-subline">
                  <span className="asset-card-meta">
                    {asset.type} · {asset.primitive}
                  </span>

                  <div className="asset-card-pqc-path">
                    <span>PQC Path</span>
                    <strong className={asset.pqcCandidate ? undefined : "asset-card-pqc-none"}>
                      {asset.pqcCandidate || migrationPath}
                    </strong>
                    {asset.pqcCandidate && <em>{migrationPath}</em>}
                  </div>
                </div>

                <div className="asset-card-footer">
                  <div className="asset-card-secondary-meta">
                    <span>Complexity {asset.complexityLevel}</span>
                    <span aria-hidden="true">·</span>
                    <span>Blast {asset.blastSeverity}</span>
                    <span aria-hidden="true">·</span>
                    <span>Impact {asset.sourceImpact}</span>
                  </div>

                  <span className="asset-card-inspect">
                    Inspect Asset <ArrowRight size={13} aria-hidden="true" />
                  </span>
                </div>
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
