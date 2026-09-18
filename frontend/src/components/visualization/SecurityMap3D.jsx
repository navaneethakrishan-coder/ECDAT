import { useEffect, useImperativeHandle, useRef, useState } from "react";

import { STRATEGY_META, displayName } from "./securityMapModel";
import { SecurityMapScene } from "./SecurityMapScene";

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

/**
 * React wrapper around the imperative three.js scene. Loaded lazily, so
 * three.js is only downloaded when the 3D map is actually shown. All
 * props are display state: the model (real findings + recorded edges),
 * which bom_refs are visible / match the search, and the focused bom_ref.
 */
export default function SecurityMap3D({
  ref,
  model,
  visibleRefs,
  searchRefs,
  focusedRef,
  relatedRefs,
  reducedMotion,
  onSelect,
  onContextLost,
}) {
  const containerRef = useRef(null);
  const labelLayerRef = useRef(null);
  const tooltipRef = useRef(null);
  const sceneRef = useRef(null);
  const callbacksRef = useRef({ onSelect, onContextLost });
  const initialReducedMotionRef = useRef(reducedMotion);
  const [hoveredRef, setHoveredRef] = useState(null);

  useEffect(() => {
    callbacksRef.current = { onSelect, onContextLost };
  }, [onSelect, onContextLost]);

  useEffect(() => {
    const scene = new SecurityMapScene({
      container: containerRef.current,
      labelLayer: labelLayerRef.current,
      tooltip: tooltipRef.current,
      reducedMotion: initialReducedMotionRef.current,
      onHover: (bomRef) => setHoveredRef(bomRef),
      onSelect: (bomRef) => callbacksRef.current.onSelect?.(bomRef, { fromScene: true }),
      onContextLost: () => callbacksRef.current.onContextLost?.(),
    });
    sceneRef.current = scene;
    return () => {
      scene.dispose();
      sceneRef.current = null;
    };
    // Created once per mount; later prop changes are pushed by the effects below.
  }, []);

  useEffect(() => {
    sceneRef.current?.setModel(model);
  }, [model]);

  useEffect(() => {
    sceneRef.current?.setState({ focusedRef, visibleRefs, searchRefs, relatedRefs });
  }, [model, focusedRef, visibleRefs, searchRefs, relatedRefs]);

  useEffect(() => {
    sceneRef.current?.setReducedMotion(reducedMotion);
  }, [reducedMotion]);

  useImperativeHandle(
    ref,
    () => ({
      fitAll: (options) => sceneRef.current?.fitAll(options),
      resetView: (options) => sceneRef.current?.resetView(options),
      focusNode: (bomRef, options) => sceneRef.current?.focusNode(bomRef, options),
      focusRegion: (regionKey, options) => sceneRef.current?.focusRegion(regionKey, options),
    }),
    [],
  );

  const hovered = hoveredRef ? model?.byRef.get(hoveredRef) : null;

  return (
    <div className="security-map-3d">
      <div ref={containerRef} className="security-map-canvas-host" />
      <div ref={labelLayerRef} className="security-map-label-layer" aria-hidden="true" />
      <div
        ref={tooltipRef}
        className={`security-map-tooltip${hovered ? " is-visible" : ""}`}
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
