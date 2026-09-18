import { useEffect, useState } from "react";
import { ListTree, Network, Orbit } from "lucide-react";

import { getBlastRadiusGraph } from "../../api";
import { SeverityBadge } from "../Badge";
import { BlastSpatialView } from "./BlastSpatialView";

const MAX_FAN_OUT = 5;

function shortRef(bomRef) {
  return bomRef ? `${bomRef.slice(0, 8)}…` : "";
}

// "private-key@<uuid>" names repeat the bom_ref; show the kind plus a short ref.
function displayName(node) {
  if (!node.name) {
    return "Unknown finding";
  }
  const at = node.name.indexOf("@");
  return at > 0 ? node.name.slice(0, at) : node.name;
}

function FindingNode({ node, current = false }) {
  const facts = [node.asset_type, node.category].filter(Boolean).join(" · ");

  return (
    <div
      className={`blast-node${current ? " blast-node-current" : ""}${node.known_finding === false ? " blast-node-unknown" : ""}`}
      data-bom-ref={node.bom_ref}
      title={`${node.name || "Unknown finding"}\nbom-ref ${node.bom_ref}${
        node.source_files?.length ? `\n${node.source_files.join("\n")}` : ""
      }`}
    >
      {current && <span className="blast-node-label">This finding</span>}
      <strong>{displayName(node)}</strong>
      <code>{shortRef(node.bom_ref)}</code>
      <span className="blast-node-facts">
        {node.known_finding === false ? "Not in the inventory" : facts || "Type not recorded"}
      </span>
      {node.occurrence_count !== null && node.occurrence_count !== undefined && (
        <span className="blast-node-facts">
          {node.occurrence_count} occurrence(s) · {node.source_files.length} file(s)
        </span>
      )}
    </div>
  );
}

/** Indirect dependents reached through `parent`, following recorded edges only. */
function IndirectChildren({ parent, indirect, visited }) {
  const children = indirect.filter((node) => node.via.includes(parent.bom_ref) && !visited.has(node.bom_ref));

  if (children.length === 0) {
    return null;
  }

  const nextVisited = new Set([...visited, ...children.map((node) => node.bom_ref)]);

  return (
    <ul className="blast-indirect" aria-label="Indirectly affected findings">
      {children.map((node) => (
        <li key={node.bom_ref}>
          <span className="blast-indirect-label">↳ depends on {displayName(parent)} {shortRef(parent.bom_ref)}</span>
          <FindingNode node={node} />
          <IndirectChildren parent={node} indirect={indirect} visited={nextVisited} />
        </li>
      ))}
    </ul>
  );
}

function BlastDiagram({ view }) {
  const { finding, dependencies, direct_dependents: direct, indirect_dependents: indirect } = view;
  // One dependent hangs straight off the trunk; 2..MAX_FAN_OUT fan out on one
  // row; more (or narrow screens, see App.css) use the left-rail list.
  const layout = direct.length === 1 ? " blast-branches-single" : direct.length <= MAX_FAN_OUT ? " blast-branches-fan" : "";

  return (
    <div className="blast-diagram" aria-label="Recorded dependency relationships">
      <span className="blast-tier-label blast-diagram-caption">
        {direct.length > 0
          ? `Affected if migrated: ${direct.length} finding(s) depend on it${
              indirect.length > 0 ? `, ${indirect.length} more indirectly` : ""
            }`
          : "No recorded dependents"}
      </span>

      {dependencies.length > 0 && (
        <div className="blast-upstream">
          <span className="blast-tier-label">This finding depends on</span>
          <div className="blast-upstream-nodes">
            {dependencies.map((node) => (
              <FindingNode key={node.bom_ref} node={node} />
            ))}
          </div>
          <div className="blast-trunk blast-trunk-up" aria-hidden="true" />
        </div>
      )}

      <FindingNode node={{ ...finding, known_finding: true }} current />

      {direct.length > 0 ? (
        <>
          <div className="blast-trunk" aria-hidden="true" />
          <ul
            className={`blast-branches${layout}`}
            style={{ "--blast-columns": Math.min(direct.length, MAX_FAN_OUT) }}
          >
            {direct.map((node) => (
              <li key={node.bom_ref} className="blast-branch">
                <FindingNode node={node} />
                <IndirectChildren
                  parent={node}
                  indirect={indirect}
                  visited={new Set([finding.bom_ref, ...direct.map((item) => item.bom_ref)])}
                />
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="blast-none-below">No findings depend on this one in the CBOM.</p>
      )}
    </div>
  );
}

/**
 * Blast Radius: which findings are affected if this one is migrated.
 * Everything comes from GET /api/blast-radius/{bom_ref}/graph -- the
 * recorded blast radius plus the CycloneDX dependsOn edges it was built
 * from. No edge is drawn that the CBOM does not record.
 */
export function BlastRadiusPanel({ bomRef, onInvestigate }) {
  const [view, setView] = useState(null);
  // Spatial view by default; phones start on the tree, which reads
  // better at a narrow width. Both render the same recorded graph.
  const [layout, setLayout] = useState(() =>
    typeof window !== "undefined" && window.matchMedia && !window.matchMedia("(min-width: 600px)").matches ? "tree" : "spatial",
  );
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    getBlastRadiusGraph(bomRef)
      .then((data) => {
        if (!cancelled) {
          setView(data);
        }
      })
      .catch((failure) => {
        if (!cancelled) {
          setError(failure.message || "Unable to load blast radius.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [bomRef]);

  const counts = view?.counts;
  const blast = view?.blast_radius;
  const complexity = view?.migration_complexity;

  return (
    <section className="workspace-panel panel-blast-radius" aria-labelledby="blast-radius-heading" data-bom-ref={bomRef}>
      <h3 id="blast-radius-heading">
        <Network size={15} aria-hidden="true" />
        Blast Radius
        <span className="blast-question">What is affected if this finding needs migration?</span>
      </h3>

      {!view && !error && <p className="workspace-empty-note">Loading blast radius…</p>}
      {error && (
        <p className="blast-error" role="alert">
          {error}
        </p>
      )}

      {view && view.bom_ref === bomRef && (
        <>
          {view.migration_strategy && !view.migration_strategy.resolved && (
            <p className="blast-review-note">
              Blast radius describes recorded dependency impact only. It does not confirm a migration path: this
              finding&apos;s migration strategy needs review.
            </p>
          )}

          <div className="blast-metrics">
            <div className="metric-tile" data-metric="affected">
              <span>Affected findings</span>
              <strong>{counts ? counts.affected_findings : "—"}</strong>
              <small>
                {counts ? `${counts.direct_dependents} direct · ${counts.indirect_dependents} indirect` : "Not recorded"}
              </small>
            </div>
            <div className="metric-tile" data-metric="dependencies">
              <span>Dependencies</span>
              <strong>{counts ? counts.dependencies : "—"}</strong>
              <small>Findings it depends on</small>
            </div>
            <div className="metric-tile" data-metric="dependents">
              <span>Dependents</span>
              <strong>{counts ? counts.direct_dependents : "—"}</strong>
              <small>Directly depend on it</small>
            </div>
            <div className="metric-tile" data-metric="source">
              <span>Source locations</span>
              <strong>{counts ? counts.source_occurrences : "—"}</strong>
              <small>{counts ? `in ${counts.source_files} file(s)` : "Not recorded"}</small>
            </div>
            <div className="metric-tile" data-metric="blast">
              <span>Blast radius</span>
              <SeverityBadge value={blast?.severity} fallback="Not recorded" />
              <small>{blast ? `${blast.score} / 100` : "—"}</small>
            </div>
            <div className="metric-tile" data-metric="complexity">
              <span>Migration complexity</span>
              <SeverityBadge value={complexity?.level} fallback="Not recorded" />
              <small>{complexity ? `${complexity.score} / 100` : "—"}</small>
            </div>
          </div>

          {view.has_relationships ? (
            <>
              <div className="blast-view-toggle map-segmented" role="group" aria-label="Dependency view">
                <button
                  type="button"
                  className={layout === "spatial" ? "is-active" : ""}
                  aria-pressed={layout === "spatial"}
                  onClick={() => setLayout("spatial")}
                >
                  <Orbit size={14} aria-hidden="true" /> Spatial
                </button>
                <button
                  type="button"
                  className={layout === "tree" ? "is-active" : ""}
                  aria-pressed={layout === "tree"}
                  onClick={() => setLayout("tree")}
                >
                  <ListTree size={14} aria-hidden="true" /> Tree
                </button>
              </div>
              {layout === "spatial" ? <BlastSpatialView view={view} onInvestigate={onInvestigate} /> : <BlastDiagram view={view} />}
            </>
          ) : (
            <div className="blast-empty" data-state="no-relationships">
              <strong>No dependency relationships recorded</strong>
              <p>
                The CBOM records no dependsOn relationship to or from this finding, so no other finding is shown as
                affected. Its blast-radius score comes only from its own source evidence and quantum risk (see below).
              </p>
              <FindingNode node={{ ...view.finding, known_finding: true }} current />
            </div>
          )}

          <p className="blast-source-note">
            Relationships: {view.relationship_source}. Arrows point from a finding to the findings that depend on it;
            shared source files are not treated as relationships.
          </p>

          <details className="workspace-disclosure">
            <summary>Affected source locations ({counts?.source_occurrences ?? 0})</summary>
            <div>
              {view.finding.occurrences.length > 0 ? (
                <ul className="blast-locations">
                  {view.finding.occurrences.map((occurrence, index) => (
                    <li key={`${occurrence.location}-${occurrence.line}-${index}`}>
                      <code>{occurrence.location || "Unknown location"}</code>
                      <span>line {occurrence.line ?? "unknown"}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="workspace-empty-note">No source occurrence is recorded for this finding.</p>
              )}
            </div>
          </details>

          {blast && (
            <details className="workspace-disclosure">
              <summary>How the blast-radius score was recorded</summary>
              <div>
                {blast.score_breakdown && (
                  <ul className="blast-breakdown">
                    {Object.entries(blast.score_breakdown).map(([key, value]) => (
                      <li key={key}>
                        <span>{key.replaceAll("_", " ")}</span>
                        <strong>{value}</strong>
                      </li>
                    ))}
                  </ul>
                )}
                {blast.reasons.length > 0 && (
                  <ul className="blast-reasons">
                    {blast.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                )}
                <p className="blast-source-note">Recorded by the blast-radius stage — not recomputed here.</p>
              </div>
            </details>
          )}
        </>
      )}
    </section>
  );
}
