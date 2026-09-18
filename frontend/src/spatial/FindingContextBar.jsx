import { Crosshair, Maximize2, X } from "lucide-react";

import { strategyPqcPath } from "../migrationStrategy";
import { SeverityBadge } from "../components/Badge";
import { INVESTIGATION_SURFACES } from "./surfaces";

/**
 * Appears when a finding (bom_ref) is focused on the dashboard: it pins
 * the selection above the page so every section below reads as one
 * investigation, and offers direct entry points into the investigation
 * workspace's surfaces. All values come from the dashboard's existing
 * finding list; nothing is fetched or derived here.
 */
export function FindingContextBar({ finding, onLocate, onInvestigate, onClear }) {
  if (!finding) return null;

  const path = strategyPqcPath(finding.migrationStrategy, finding.strategyPqcComponent);
  const severity = String(finding.riskSeverity || "unknown").toLowerCase();

  return (
    <aside
      className={`finding-context-bar finding-context-${severity}`}
      aria-label={`Focused finding ${finding.name}`}
      data-bom-ref={finding.bomRef}
    >
      <div className="finding-context-identity">
        <span className="finding-context-beacon" aria-hidden="true" />
        <div>
          <span className="finding-context-eyebrow">Focused finding</span>
          <strong>{finding.name}</strong>
          <code title={finding.bomRef}>{finding.bomRef}</code>
        </div>
      </div>

      <dl className="finding-context-facts">
        <div>
          <dt>Risk</dt>
          <dd>
            {typeof finding.riskScore === "number" ? finding.riskScore : "—"} <SeverityBadge value={finding.riskSeverity} />
          </dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>
            <SeverityBadge value={finding.priorityLevel} />
          </dd>
        </div>
        <div>
          <dt>Migration</dt>
          <dd className={path?.none ? "finding-context-none" : "finding-context-pqc"}>
            {path ? (path.label ? `${path.text} · ${path.label}` : path.text) : "Not recorded"}
          </dd>
        </div>
      </dl>

      <div className="finding-context-actions">
        <button type="button" className="btn btn-outline btn-sm" onClick={() => onLocate(finding.bomRef)}>
          <Crosshair size={14} aria-hidden="true" />
          Locate in map
        </button>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => onInvestigate(finding.bomRef, null)}>
          <Maximize2 size={14} aria-hidden="true" />
          Investigate
        </button>
        <div className="finding-context-branches" role="group" aria-label="Open an investigation surface">
          {INVESTIGATION_SURFACES.map((surface) => (
            <button
              type="button"
              key={surface.key}
              className="finding-context-branch"
              onClick={() => onInvestigate(finding.bomRef, surface.key)}
              aria-label={`Investigate ${surface.label} for ${finding.name}`}
              title={surface.label}
            >
              <surface.icon size={14} aria-hidden="true" />
            </button>
          ))}
        </div>
        <button type="button" className="finding-context-clear" onClick={onClear} aria-label="Clear focused finding">
          <X size={15} />
        </button>
      </div>
    </aside>
  );
}
