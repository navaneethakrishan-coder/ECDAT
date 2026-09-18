import { useEffect, useImperativeHandle, useRef, useState } from "react";
import { Vector3 } from "three";

import { STRATEGY_META, displayName } from "../../components/visualization/securityMapModel";
import { EnvironmentLayer } from "../engine/EnvironmentLayer";
import { INVESTIGATION_DIRECTION, InvestigationLayer } from "../engine/InvestigationLayer";
import { LandscapeLayer } from "../engine/LandscapeLayer";
import { PostureLayer } from "../engine/PostureLayer";
import { SimulationLayer } from "../engine/SimulationLayer";
import { DEFAULT_DIRECTION, SpatialEngine } from "../engine/SpatialEngine";

const GLOBAL_DIRECTION = new Vector3(0.28, 0.95, 1).normalize();
const SIMULATION_DIRECTION = new Vector3(0.1, 0.45, 1).normalize();

// How present each part of the world is in each view (1 = full).
const PRESENCE = {
  global: { posture: 1, landscape: 0.8 },
  map: { posture: 0.3, landscape: 1 },
  finding: { posture: 0.2, landscape: 1 },
  investigation: { posture: 0.12, landscape: 0.45 },
  simulation: { posture: 0.12, landscape: 0.4 },
};

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

/**
 * The shared 3D stage: ONE SpatialEngine (one renderer, one canvas, one
 * camera) holding every spatial layer -- environment, posture,
 * cryptographic landscape, investigation space and simulation space.
 *
 * React owns all state; this component only pushes it into the layers and
 * lets the camera director frame the current view. Picks are reported
 * back as bom_refs / surface keys / metric keys to App's existing flows.
 * Loaded lazily so three.js is only downloaded when the stage is used.
 */
export default function SpatialStage({
  ref,
  model,
  visibleRefs,
  searchRefs,
  focusedRef,
  relatedRefs,
  view,
  activeSurface,
  simulation,
  investigation,
  posture,
  activeMetric,
  insets,
  tier,
  reducedMotion,
  onSelectFinding,
  onSurface,
  onMetric,
  onContextLost,
}) {
  const hostRef = useRef(null);
  const labelLayerRef = useRef(null);
  const tooltipRef = useRef(null);
  const stageRef = useRef(null);
  const callbacksRef = useRef({ onSelectFinding, onSurface, onMetric, onContextLost });
  const initialRef = useRef({ reducedMotion, tier });
  const [hoveredRef, setHoveredRef] = useState(null);

  useEffect(() => {
    callbacksRef.current = { onSelectFinding, onSurface, onMetric, onContextLost };
  }, [onSelectFinding, onSurface, onMetric, onContextLost]);

  // ---- create the single engine and its layers (once per mount)
  useEffect(() => {
    const desktop = initialRef.current.tier === "desktop";
    const engine = new SpatialEngine({
      container: hostRef.current,
      labelLayer: labelLayerRef.current,
      reducedMotion: initialRef.current.reducedMotion,
      canvasClassName: "spatial-stage-canvas",
      pixelRatioCap: desktop ? 2 : 1,
      maxDistance: 140,
      onContextLost: () => callbacksRef.current.onContextLost?.(),
    });
    const environment = engine.addLayer(new EnvironmentLayer({ size: 96, structures: desktop, particles: desktop }));
    environment.group.position.set(0, 0, -8);
    const posture = engine.addLayer(new PostureLayer({ onMetric: (key) => callbacksRef.current.onMetric?.(key) }));
    const landscape = engine.addLayer(
      new LandscapeLayer({
        tooltip: tooltipRef.current,
        onHover: (bomRef) => setHoveredRef(bomRef),
        onSelect: (bomRef) => callbacksRef.current.onSelectFinding?.(bomRef),
        onClear: () => callbacksRef.current.onSelectFinding?.(null),
      }),
    );
    const investigationLayer = engine.addLayer(
      new InvestigationLayer({ landscape, onSurface: (key) => callbacksRef.current.onSurface?.(key) }),
    );
    const simulationLayer = engine.addLayer(new SimulationLayer({ landscape }));
    stageRef.current = { engine, environment, posture, landscape, investigation: investigationLayer, simulation: simulationLayer };
    return () => {
      engine.dispose();
      stageRef.current = null;
    };
  }, []);

  // ---- push React state into the layers
  useEffect(() => {
    stageRef.current?.landscape.setModel(model);
  }, [model]);

  useEffect(() => {
    stageRef.current?.landscape.setState({ focusedRef, visibleRefs, searchRefs, relatedRefs });
  }, [model, focusedRef, visibleRefs, searchRefs, relatedRefs]);

  useEffect(() => {
    stageRef.current?.posture.setPosture(posture);
  }, [posture]);

  useEffect(() => {
    stageRef.current?.posture.setActiveMetric(activeMetric);
  }, [activeMetric, posture]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const presence = PRESENCE[view] || PRESENCE.global;
    stage.posture.setPresence(presence.posture);
    stage.landscape.setEmphasis(presence.landscape);
  }, [view]);

  const investigationFocus =
    (view === "investigation" || view === "simulation") && focusedRef && model
      ? {
          bomRef: focusedRef,
          activeSurface,
          summaries: investigation?.summaries,
          stages: investigation?.stages,
          evidenceSteps: investigation?.evidenceSteps,
          heightScale: model.bounds.height,
        }
      : null;

  useEffect(() => {
    stageRef.current?.investigation.setFocus(investigationFocus);
  });

  useEffect(() => {
    const active = view === "simulation" && simulation?.bomRef === focusedRef ? simulation : null;
    stageRef.current?.simulation.setSimulation(active, model?.bounds.height || 12);
  }, [view, simulation, focusedRef, model]);

  useEffect(() => {
    stageRef.current?.engine.setReducedMotion(reducedMotion);
  }, [reducedMotion]);

  const insetKey = `${Math.round(insets?.left || 0)}|${Math.round(insets?.right || 0)}|${Math.round(insets?.top || 0)}|${Math.round(
    insets?.bottom || 0,
  )}`;

  // ---- camera director: frame the current view
  const directorRef = useRef(null);
  // The director always reads the latest props; refreshed after each render.
  useEffect(() => {
    directorRef.current = ({ animate = true } = {}) => {
      const stage = stageRef.current;
      if (!stage || !model) return;
      const { engine, landscape, posture: postureLayer, investigation: investigationLayer, simulation: simulationLayer } = stage;
      let frame = null;
      switch (view) {
        case "global":
          frame = engine.frameFor([...landscape.allPositions(), ...postureLayer.anchorPositions()], GLOBAL_DIRECTION, 6, { fill: 0.9 });
          break;
        case "map":
          frame = engine.frameFor(landscape.visiblePositions(), DEFAULT_DIRECTION, 6);
          break;
        case "finding":
          frame = focusedRef ? engine.frameFor(landscape.focusPositions(focusedRef), DEFAULT_DIRECTION, 5) : null;
          break;
        case "investigation": {
          const points = investigationLayer.framePoints();
          frame = points.length ? engine.frameFor(points, INVESTIGATION_DIRECTION, 4.5, { lift: 1.6 }) : null;
          break;
        }
        case "simulation": {
          const points = [...simulationLayer.framePoints(), ...investigationLayer.framePoints().slice(0, 1)];
          frame = points.length ? engine.frameFor(points, SIMULATION_DIRECTION, 4, { lift: 1.8 }) : null;
          break;
        }
        default:
          break;
      }
      if (frame) engine.moveCamera(frame, { animate, duration: 900 });
    };
  });

  const directorKey = `${view}|${focusedRef || ""}|${activeSurface || ""}|${simulation?.bomRef === focusedRef ? JSON.stringify(simulation?.risk) : ""}|${
    investigation?.evidenceSteps?.length || 0
  }`;
  const framedOnce = useRef(false);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const [left, right, top, bottom] = insetKey.split("|").map(Number);
    stage.engine.setInsets({ left, right, top, bottom });
  }, [insetKey]);

  useEffect(() => {
    if (!model) return;
    const animate = framedOnce.current;
    framedOnce.current = true;
    const frame = requestAnimationFrame(() => directorRef.current?.({ animate }));
    return () => cancelAnimationFrame(frame);
  }, [directorKey, insetKey, model]);

  useImperativeHandle(
    ref,
    () => ({
      resetView: () => directorRef.current?.(),
      fitAll: () => {
        const stage = stageRef.current;
        if (stage) stage.engine.moveCamera(stage.engine.frameFor(stage.landscape.visiblePositions()));
      },
      focusSelected: (bomRef) => {
        const stage = stageRef.current;
        if (!stage || !bomRef) return;
        stage.engine.moveCamera(stage.engine.frameFor(stage.landscape.focusPositions(bomRef), stage.engine.currentDirection(), 5));
      },
      focusRegion: (regionKey) => {
        const stage = stageRef.current;
        if (stage) stage.engine.moveCamera(stage.engine.frameFor(stage.landscape.regionPositions(regionKey)));
      },
    }),
    [],
  );

  const hovered = hoveredRef ? model?.byRef.get(hoveredRef) : null;

  return (
    <div className="spatial-stage" data-view={view}>
      <div ref={hostRef} className="spatial-stage-host" />
      <div ref={labelLayerRef} className="spatial-stage-labels security-map-label-layer" aria-hidden="true" />
      <div
        ref={tooltipRef}
        className={`security-map-tooltip spatial-stage-tooltip${hovered ? " is-visible" : ""}`}
        role="tooltip"
        aria-hidden={hovered ? undefined : "true"}
      >
        {hovered && (
          <>
            <strong>{displayName(hovered)}</strong>
            <dl>
              <div>
                <dt>Family</dt>
                <dd>{hovered.family || "Not recorded"}</dd>
              </div>
              <div>
                <dt>Risk</dt>
                <dd>
                  {formatScore(hovered.riskScore)} · {hovered.riskSeverity}
                </dd>
              </div>
              <div>
                <dt>Priority</dt>
                <dd>
                  {formatScore(hovered.priorityScore)} · {hovered.priorityLevel}
                </dd>
              </div>
              <div>
                <dt>Strategy</dt>
                <dd>{STRATEGY_META[hovered.strategy]?.label || "No strategy recorded"}</dd>
              </div>
            </dl>
          </>
        )}
      </div>
    </div>
  );
}
