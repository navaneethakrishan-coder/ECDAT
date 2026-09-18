import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft } from "lucide-react";

import { InvestigationHub } from "../spatial/InvestigationHub";
import { scrollBehavior } from "../spatial/motion";
import { useScrollSpy } from "../spatial/useScrollSpy";
import { AIAdvisorPanel } from "./AIAdvisorPanel";
import { ErrorState } from "./States";
import { AssetHeaderBand } from "./detail/AssetHeaderBand";
import { BlastRadiusPanel } from "./detail/BlastRadiusPanel";
import { EvidenceExplorer } from "./detail/EvidenceExplorer";
import { EvidencePanel } from "./detail/EvidencePanel";
import { MigrationFlow } from "./detail/MigrationFlow";
import { RiskImpactPanel } from "./detail/RiskImpactPanel";

const SPY_TARGETS = [
  { key: "risk", selector: "#surface-risk" },
  { key: "migration", selector: "#surface-migration" },
  { key: "blast", selector: "#surface-blast" },
  { key: "evidence", selector: "#surface-evidence" },
  { key: "ai", selector: "#surface-ai" },
];

function Surface({ id, activeSurface, depth = "primary", focusable = false, children }) {
  // What-If lives inside the Migration surface, so it focuses that one.
  const focusKey = activeSurface === "whatif" ? "migration" : activeSurface;
  const state = !activeSurface ? "overview" : focusKey === id ? "focused" : "receded";
  return (
    <div
      id={`surface-${id}`}
      className={`investigation-surface surface-depth-${depth} is-${state}${
        activeSurface === "whatif" && id === "migration" ? " is-focus-whatif" : ""
      }`}
      data-surface={id}
      tabIndex={focusable ? -1 : undefined}
    >
      {children}
    </div>
  );
}

/**
 * The investigation workspace for one finding (bom_ref), composed as a
 * spatial environment: the finding sits at the centre of the
 * Investigation Hub and each analysis surface is a connected branch.
 * Choosing a branch brings that surface forward and lets the others
 * recede; the finding itself returns to the overview.
 *
 *   [ header band: identity · risk · priority · decision ]
 *   [ hub ]  [ Risk        ]
 *            [ Migration + What-If ]
 *            [ Blast Radius ]
 *            [ Evidence + Evidence Explorer ]
 *            [ AI Analysis ]
 *
 * The panels read the GET /api/asset/{bom_ref} record App.jsx already
 * fetched; Blast Radius, the Evidence Explorer and the What-If
 * Simulator make their own bom_ref-addressed requests. Nothing here
 * changes what they show.
 */
export function AssetDetailPanel({
  assetName,
  assetDetail,
  loading,
  error,
  onRetry,
  onClose,
  aiStatus,
  aiAdvice,
  aiError,
  onGenerateAdvice,
  activeSurface = null,
  onSurfaceChange,
  previousFinding = null,
  onBack,
  onInvestigate,
  onEvidence,
  layout = "overlay",
}) {
  // "overlay": the modal workspace of the scrolling layout.
  // "inspector": docked beside the shared 3D stage (non-modal).
  const inspector = layout === "inspector";
  const [workspace, setWorkspace] = useState(null);
  const scrolledInitially = useRef(false);

  const workspaceRef = useCallback((element) => setWorkspace(element), []);
  const ready = Boolean(assetDetail) && !loading;
  const spyTargets = useMemo(() => SPY_TARGETS, []);
  const inViewSurface = useScrollSpy(spyTargets, {
    root: workspace,
    enabled: ready && Boolean(workspace),
    rootMargin: "-25% 0px -55% 0px",
  });

  const bringForward = useCallback(
    (key) => {
      if (!workspace) return;
      const target =
        key === "whatif"
          ? workspace.querySelector("#surface-migration .what-if")
          : key
          ? workspace.querySelector(`#surface-${key}`)
          : workspace.querySelector(".workspace-header");
      target?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
      // In the docked inspector, keyboard focus follows the surface brought forward.
      if (inspector && key) {
        const surface = key === "whatif" ? workspace.querySelector("#surface-migration") : target;
        surface?.focus({ preventScroll: true });
      }
    },
    [workspace, inspector],
  );

  // Entering the workspace for a specific surface (from the map, the
  // focus bar or a dashboard shortcut) brings it forward once loaded.
  useEffect(() => {
    if (!ready || !workspace || scrolledInitially.current) return;
    scrolledInitially.current = true;
    if (activeSurface) {
      const frame = requestAnimationFrame(() => bringForward(activeSurface));
      return () => cancelAnimationFrame(frame);
    }
    return undefined;
  }, [ready, workspace, activeSurface, bringForward]);

  function focusSurface(key) {
    onSurfaceChange?.(key);
    bringForward(key);
  }

  const phase = loading ? "loading" : assetDetail ? "ready" : "error";

  return (
    <div
      ref={workspaceRef}
      className={inspector ? "stage-inspector" : "asset-workspace spatial-workspace"}
      role={inspector ? "region" : "dialog"}
      aria-modal={inspector ? undefined : "true"}
      aria-label={`${assetName} investigation`}
      data-phase={phase}
      data-bom-ref={assetDetail?.bom_ref || undefined}
    >
      <div className="asset-workspace-topbar">
        <div className="workspace-trail">
          {previousFinding && onBack && (
            <button type="button" className="workspace-back" onClick={onBack}>
              <ArrowLeft size={14} aria-hidden="true" />
              Back to {previousFinding.name}
            </button>
          )}
          <div className="breadcrumb">{inspector ? "Investigation space" : "Asset Investigation"} / {assetName}</div>
        </div>
        <button type="button" className="asset-detail-close" onClick={onClose}>
          Close
        </button>
      </div>

      {loading ? (
        <div className="asset-detail-loading" role="status">
          <div className="loading-spinner" />
          <p>Loading asset analysis...</p>
        </div>
      ) : assetDetail ? (
        <>
          <AssetHeaderBand assetName={assetName} assetDetail={assetDetail} />

          <div className={`investigation-layout${activeSurface ? " has-focus" : ""}`}>
            <aside className="investigation-hub-column">
              <InvestigationHub
                assetName={assetName}
                assetDetail={assetDetail}
                activeSurface={activeSurface}
                inViewSurface={inViewSurface}
                aiStatus={aiStatus}
                onFocusSurface={focusSurface}
              />
            </aside>

            <div className="investigation-surfaces">
              <Surface id="risk" activeSurface={activeSurface} depth="secondary" focusable={inspector}>
                <RiskImpactPanel assetDetail={assetDetail} />
              </Surface>

              <Surface id="migration" activeSurface={activeSurface} focusable={inspector}>
                <MigrationFlow assetDetail={assetDetail} />
              </Surface>

              {assetDetail.bom_ref && (
                <Surface id="blast" activeSurface={activeSurface} focusable={inspector}>
                  <BlastRadiusPanel
                    key={`blast-${assetDetail.bom_ref}`}
                    bomRef={assetDetail.bom_ref}
                    onInvestigate={onInvestigate}
                  />
                </Surface>
              )}

              <Surface id="evidence" activeSurface={activeSurface} depth="secondary" focusable={inspector}>
                <EvidencePanel assetDetail={assetDetail} />
                {assetDetail.bom_ref && (
                  <EvidenceExplorer key={assetDetail.bom_ref} bomRef={assetDetail.bom_ref} onEvidence={onEvidence} />
                )}
              </Surface>

              <Surface id="ai" activeSurface={activeSurface} focusable={inspector}>
                <AIAdvisorPanel
                  assetName={assetName}
                  assetDetail={assetDetail}
                  status={aiStatus}
                  advice={aiAdvice}
                  error={aiError}
                  onGenerate={onGenerateAdvice}
                />
              </Surface>
            </div>
          </div>
        </>
      ) : (
        <div className="asset-detail-loading">
          <ErrorState message={error || "Unable to load asset analysis."} onRetry={onRetry} />
        </div>
      )}
    </div>
  );
}
