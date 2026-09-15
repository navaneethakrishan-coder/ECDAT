import { Gauge } from "lucide-react";

import { SeverityBadge } from "../Badge";

/**
 * Left column, row 1 of the workspace grid. The headline risk figure
 * already lives in the header band above -- this panel holds the
 * *supporting* risk dimensions (complexity, blast radius, source
 * impact) as a secondary metric tier, plus the plain-language "why
 * this priority" explanation the backend already returns but the
 * previous layout buried at the bottom of a long stack.
 */
export function RiskImpactPanel({ assetDetail }) {
  const explanation = assetDetail?.priority?.migration_priority?.explanation;
  const sourceImpact = assetDetail?.source_impact || {};

  const complexityLevel = assetDetail?.complexity?.level;
  const complexityScore = assetDetail?.complexity?.score;

  const blastSeverity = assetDetail?.blast_radius?.severity;
  const blastScore =
    assetDetail?.blast_radius?.blast_radius_score ??
    assetDetail?.blast_radius?.score ??
    assetDetail?.blast_radius_score;

  return (
    <section className="workspace-panel panel-risk-impact" aria-labelledby="risk-impact-heading">
      <h3 id="risk-impact-heading">
        <Gauge size={15} aria-hidden="true" />
        Risk Intelligence
      </h3>

      <div className="metric-tier">
        <div className="metric-tile">
          <span>Migration Complexity</span>
          <SeverityBadge value={complexityLevel} fallback="—" />
          <small>{complexityScore ?? "—"} / 100</small>
        </div>

        <div className="metric-tile">
          <span>Blast Radius</span>
          <SeverityBadge value={blastSeverity} fallback="—" />
          <small>{blastScore ?? "—"} / 100</small>
        </div>

        <div className="metric-tile">
          <span>Source Impact</span>
          <SeverityBadge value={sourceImpact.impact_level} fallback="—" />
          <small>
            {sourceImpact.affected_file_count ?? 0} files · {sourceImpact.affected_function_count ?? 0} fns
          </small>
        </div>
      </div>

      {explanation?.summary && (
        <p className="workspace-explanation">
          <strong>Why this priority —</strong> {explanation.summary}
          {Array.isArray(explanation.reasons) && explanation.reasons.length > 0 && (
            <span className="workspace-explanation-reasons"> {explanation.reasons.join(" ")}</span>
          )}
        </p>
      )}
    </section>
  );
}
