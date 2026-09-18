import { Suspense, lazy, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronRight, Crosshair, PanelLeftClose, PanelLeftOpen, RotateCcw, Scan } from "lucide-react";

import { INVESTIGATION_SURFACES } from "../surfaces";
import "./stage.css";

const SpatialStage = lazy(() => import("./SpatialStage"));

const STAGE_SECTIONS = [
  { key: "posture", label: "Posture" },
  { key: "operations", label: "Operations" },
  { key: "landscape", label: "Landscape" },
  { key: "intelligence", label: "Intelligence" },
  { key: "findings", label: "Findings" },
];

const VIEW_LABELS = {
  global: "Global security space",
  map: "Cryptographic landscape",
  finding: "Finding focus",
  investigation: "Investigation space",
  simulation: "Simulation space",
};

/**
 * Desktop / tablet application shell around the shared 3D stage.
 *
 *   z0  SpatialStage (one fixed canvas, lazy)      — the world
 *   z1  projected labels                           — inside SpatialStage
 *   z2  HUD: nav rail · command bar · focus bar · view path · camera
 *   z3  docks: section dock (left) · investigation inspector (right)
 *
 * The docks hold the existing React panels unchanged; their measured
 * size is reported to the stage so the camera frames the uncovered area.
 */
export function StageLayout({
  tier,
  view,
  section,
  onSection,
  stageProps,
  stageRef,
  sidebar,
  topbar,
  contextBar,
  docks,
  inspector,
  focusedName,
  activeSurface,
  onEscape,
  onGoGlobal,
  onGoLandscape,
  onGoFinding,
  onGoInvestigation,
}) {
  const [dockOpen, setDockOpen] = useState(true);
  const [insets, setInsets] = useState({ left: 0, right: 0, top: 0, bottom: 0 });
  const topRef = useRef(null);
  const dockRef = useRef(null);
  const inspectorRef = useRef(null);
  const controlsRef = useRef(null);

  // The stage owns the viewport: no page scroll, docks scroll internally.
  useEffect(() => {
    document.documentElement.classList.add("is-stage-layout");
    return () => document.documentElement.classList.remove("is-stage-layout");
  }, []);

  // Measure what the docks cover so the camera frames the rest.
  useLayoutEffect(() => {
    function measure() {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const next = { left: 0, right: 0, top: 0, bottom: 0 };
      const rail = document.querySelector(".stage-shell .sidebar");
      if (rail) next.left = rail.getBoundingClientRect().right;
      if (topRef.current) next.top = topRef.current.getBoundingClientRect().bottom;
      if (controlsRef.current) next.bottom = height - controlsRef.current.getBoundingClientRect().top;
      [dockRef.current, inspectorRef.current].forEach((element) => {
        if (!element) return;
        const rect = element.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        if (rect.width > (width - next.left) * 0.8) {
          // Bottom sheet (tablet).
          next.bottom = Math.max(next.bottom, height - rect.top);
        } else if (rect.left < width / 2) {
          next.left = Math.max(next.left, rect.right);
        } else {
          next.right = Math.max(next.right, width - rect.left);
        }
      });
      setInsets((current) =>
        ["left", "right", "top", "bottom"].every((key) => Math.abs(current[key] - next[key]) < 2) ? current : next,
      );
    }
    measure();
    const observer = new ResizeObserver(measure);
    [topRef.current, dockRef.current, inspectorRef.current, controlsRef.current].forEach((element) => element && observer.observe(element));
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [dockOpen, inspector, section, view, tier]);

  // Esc steps back one level of the spatial hierarchy.
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      onEscape();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onEscape]);

  const showDock = !inspector && dockOpen;
  // "private-key@<bom-ref>" names repeat the identity; the path shows the kind.
  const shortName = focusedName ? String(focusedName).split("@")[0] : null;
  const surfaceLabel = INVESTIGATION_SURFACES.find((surface) => surface.key === activeSurface)?.label;
  const announcement = [
    VIEW_LABELS[view],
    shortName && view !== "global" && view !== "map" ? shortName : null,
    surfaceLabel && (view === "investigation" || view === "simulation") ? `${surfaceLabel} surface` : null,
  ]
    .filter(Boolean)
    .join(" — ");

  const path = [
    { key: "global", label: "Global", onClick: onGoGlobal, current: view === "global" },
    { key: "map", label: "Landscape", onClick: onGoLandscape, current: view === "map" },
  ];
  if (shortName && view !== "global") path.push({ key: "finding", label: shortName, onClick: onGoFinding, current: view === "finding" });
  if (view === "investigation" || view === "simulation")
    path.push({ key: "investigation", label: surfaceLabel ? `Investigation · ${surfaceLabel}` : "Investigation", onClick: onGoInvestigation, current: view === "investigation" });
  if (view === "simulation") path.push({ key: "simulation", label: "Simulation", onClick: null, current: true });

  return (
    <div className="app-shell stage-shell" data-view={view} data-tier={tier}>
      <Suspense
        fallback={
          <div className="spatial-stage spatial-stage-loading" role="status">
            <span>Preparing spatial stage…</span>
          </div>
        }
      >
        <SpatialStage ref={stageRef} {...stageProps} view={view} insets={insets} tier={tier} />
      </Suspense>

      {sidebar}

      <div className="stage-hud" data-dock={showDock ? "open" : "closed"} data-inspector={inspector ? "open" : "closed"}>
        <div className="stage-top" ref={topRef}>
          {topbar}
          {contextBar}
        </div>

        {!inspector && (
          <button
            type="button"
            className="stage-dock-toggle"
            onClick={() => setDockOpen((open) => !open)}
            aria-expanded={dockOpen}
            aria-controls="stage-section-dock"
          >
            {dockOpen ? <PanelLeftClose size={15} aria-hidden="true" /> : <PanelLeftOpen size={15} aria-hidden="true" />}
            {dockOpen ? "Hide panel" : "Show panel"}
          </button>
        )}

        {showDock && (
          <aside className="stage-dock stage-dock-left" id="stage-section-dock" ref={dockRef} aria-label="Workspace panel">
            <div className="stage-dock-tabs" role="tablist" aria-label="Workspace sections">
              {STAGE_SECTIONS.map((item) => (
                <button
                  type="button"
                  key={item.key}
                  role="tab"
                  id={`stage-tab-${item.key}`}
                  aria-selected={section === item.key}
                  aria-controls="stage-dock-panel"
                  className={section === item.key ? "is-active" : ""}
                  onClick={() => onSection(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="stage-dock-body" id="stage-dock-panel" role="tabpanel" aria-labelledby={`stage-tab-${section}`}>
              {docks[section]}
            </div>
          </aside>
        )}

        {inspector && (
          <aside className="stage-dock stage-dock-right" ref={inspectorRef} aria-label="Investigation inspector">
            {inspector}
          </aside>
        )}

        <div className="stage-controls" ref={controlsRef}>
          <nav className="stage-path" aria-label="Spatial location">
            {path.map((step, index) => (
              <span key={step.key} className="stage-path-step">
                {index > 0 && <ChevronRight size={13} aria-hidden="true" />}
                <button
                  type="button"
                  onClick={step.onClick || undefined}
                  disabled={!step.onClick || step.current}
                  aria-current={step.current ? "location" : undefined}
                  className={step.current ? "is-current" : ""}
                >
                  {step.label}
                </button>
              </span>
            ))}
          </nav>
          <div className="stage-camera" role="group" aria-label="Camera">
            <button type="button" className="map-icon-button" onClick={() => stageRef.current?.resetView()} aria-label="Reset view">
              <RotateCcw size={14} /> <span>Reset</span>
            </button>
            <button type="button" className="map-icon-button" onClick={() => stageRef.current?.fitAll()} aria-label="Fit all findings">
              <Scan size={14} /> <span>Fit all</span>
            </button>
            <button
              type="button"
              className="map-icon-button"
              onClick={() => stageRef.current?.focusSelected(stageProps.focusedRef)}
              disabled={!stageProps.focusedRef}
              aria-label="Focus selected finding"
            >
              <Crosshair size={14} /> <span>Focus selected</span>
            </button>
            {stageProps.model && (
              <label className="map-region-select">
                <span className="sr-only">Focus a cryptographic role region</span>
                <select
                  name="stage-region"
                  value=""
                  onChange={(event) => {
                    if (event.target.value) stageRef.current?.focusRegion(event.target.value);
                  }}
                >
                  <option value="">Focus region…</option>
                  {stageProps.model.regions.map((region) => (
                    <option key={region.key} value={region.key}>
                      {region.label} ({region.count})
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </div>

        <p className="sr-only" aria-live="polite" data-stage-announcement>
          {announcement}
        </p>
      </div>
    </div>
  );
}
