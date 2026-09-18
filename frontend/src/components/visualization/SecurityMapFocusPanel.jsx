import { Crosshair, ExternalLink, X } from "lucide-react";

import { INVESTIGATION_SURFACES } from "../../spatial/surfaces";
import { SeverityBadge } from "../Badge";
import { StrategyGlyph } from "./SecurityMapLegend";
import { STRATEGY_META, displayName, shortRef } from "./securityMapModel";

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

/**
 * PQC path exactly as the strategy layer decided it. Only DIRECT_PQC /
 * HYBRID have a selected component; a NEEDS_REVIEW ranking-model
 * candidate is shown only as "not selected".
 */
function PqcPath({ node }) {
  if (node.strategy === "DIRECT_PQC" || node.strategy === "HYBRID") {
    return node.selectedComponent ? (
      <dd className="map-focus-pqc">
        {node.selectedComponent}
        <span>
          {node.strategy === "HYBRID"
            ? `Selected hybrid path${node.classicalComponent ? ` alongside ${node.classicalComponent}` : ""}`
            : "Selected direct PQC path"}
          {node.pqcFamily ? ` · ${node.pqcFamily}` : ""}
        </span>
      </dd>
    ) : (
      <dd className="map-focus-muted">No suitable PQC component recorded</dd>
    );
  }

  if (node.strategy === "NEEDS_REVIEW") {
    return (
      <dd className="map-focus-review">
        No PQC component selected — migration requires review
        {node.rankingCandidate && (
          <span className="map-focus-ranking">Ranking-model candidate — not selected: {node.rankingCandidate}</span>
        )}
      </dd>
    );
  }

  if (node.strategy === "KEEP") {
    return <dd className="map-focus-muted">No PQC migration</dd>;
  }

  return <dd className="map-focus-muted">No migration strategy recorded</dd>;
}

function RelatedList({ title, refs, model, onFocusRef }) {
  if (!refs.length) {
    return (
      <div className="map-focus-related">
        <span>{title}</span>
        <em>None recorded</em>
      </div>
    );
  }
  return (
    <div className="map-focus-related">
      <span>
        {title} · {refs.length}
      </span>
      <ul>
        {refs.map((ref) => {
          const related = model.byRef.get(ref);
          return (
            <li key={ref}>
              <button type="button" onClick={() => onFocusRef(ref)} title={ref}>
                {related ? displayName(related) : "Unknown finding"} <code>{shortRef(ref)}</code>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Compact context for the focused finding. "Open Finding" hands the
 * bom_ref to the existing investigation workspace (App's selection);
 * this panel does not duplicate that workspace.
 */
export function SecurityMapFocusPanel({ node, model, hiddenByFilters, onOpen, onFocusRef, onCenter, onClear }) {
  const indirect = node.transitiveDependents.filter((ref) => !node.directDependents.includes(ref));
  const source = node.sourceLocations[0];

  return (
    <section className="map-focus-panel" aria-label={`Focused finding ${displayName(node)}`} data-bom-ref={node.bomRef}>
      <div className="map-focus-head">
        <span className="map-focus-eyebrow">Cryptographic finding</span>
        <button type="button" className="map-icon-button" onClick={onClear} aria-label="Clear focused finding">
          <X size={14} />
        </button>
      </div>

      <h3 className="map-focus-title">
        <StrategyGlyph strategy={node.strategy} size={20} />
        {displayName(node)}
      </h3>
      <code className="map-focus-ref" title="bom_ref">
        {node.bomRef}
      </code>

      {hiddenByFilters && <p className="map-focus-note">Hidden by the current map filters.</p>}

      <dl className="map-focus-grid">
        <div>
          <dt>Risk</dt>
          <dd>
            {formatScore(node.riskScore)} <SeverityBadge value={node.riskSeverity} />
          </dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>
            {formatScore(node.priorityScore)} <SeverityBadge value={node.priorityLevel} />
          </dd>
        </div>
        <div>
          <dt>Blast radius</dt>
          <dd>
            {formatScore(node.blastScore)} <SeverityBadge value={node.blastSeverity} />
          </dd>
        </div>
        <div>
          <dt>Complexity</dt>
          <dd>
            {formatScore(node.complexityScore)} <SeverityBadge value={node.complexityLevel} />
          </dd>
        </div>
        <div className="map-focus-wide">
          <dt>Strategy</dt>
          <dd>
            {STRATEGY_META[node.strategy]?.label || "No strategy recorded"}
            {node.strategyConfidence && <span className="map-focus-sub">confidence {node.strategyConfidence}</span>}
          </dd>
        </div>
        <div className="map-focus-wide">
          <dt>PQC path</dt>
          <PqcPath node={node} />
        </div>
        <div>
          <dt>Family</dt>
          <dd>{node.family || "Not recorded"}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{node.roleLabel || "Not recorded"}</dd>
        </div>
        <div className="map-focus-wide">
          <dt>Purpose</dt>
          <dd>
            {node.purposes.length ? node.purposes.join(", ") : "Not recorded"}
            {node.purposeConfidence && <span className="map-focus-sub">confidence {node.purposeConfidence}</span>}
          </dd>
        </div>
        <div className="map-focus-wide">
          <dt>Source</dt>
          <dd className="map-focus-source">
            {source ? (
              <>
                <code>{source.location}</code>
                {source.line !== null && <span>line {source.line}</span>}
                {node.sourceLocations.length > 1 && <span>+{node.sourceLocations.length - 1} more</span>}
              </>
            ) : (
              "No source location recorded"
            )}
          </dd>
        </div>
      </dl>

      <div className="map-focus-relations">
        <RelatedList title="Depends on" refs={node.dependencies} model={model} onFocusRef={onFocusRef} />
        <RelatedList title="Direct dependents" refs={node.directDependents} model={model} onFocusRef={onFocusRef} />
        {indirect.length > 0 && (
          <RelatedList title="Indirect dependents" refs={indirect} model={model} onFocusRef={onFocusRef} />
        )}
      </div>

      <div className="map-focus-investigate" role="group" aria-label="Investigate this finding">
        <span>Investigate</span>
        <div>
          {INVESTIGATION_SURFACES.map((surface) => (
            <button
              type="button"
              key={surface.key}
              className="map-chip"
              onClick={() => onOpen(node.bomRef, surface.key)}
              aria-label={`Open ${surface.label} for ${displayName(node)}`}
            >
              <surface.icon size={12} aria-hidden="true" />
              {surface.label}
            </button>
          ))}
        </div>
      </div>

      <div className="map-focus-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpen(node.bomRef)}>
          <ExternalLink size={14} aria-hidden="true" />
          Open Finding
        </button>
        {onCenter && (
          <button type="button" className="btn btn-outline btn-sm" onClick={() => onCenter(node.bomRef)}>
            <Crosshair size={14} aria-hidden="true" />
            Center in map
          </button>
        )}
      </div>
    </section>
  );
}
