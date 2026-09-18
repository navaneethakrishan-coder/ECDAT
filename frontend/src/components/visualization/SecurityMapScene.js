// Security Map scene for the scrolling layout (≤600px, or when the
// shared SpatialStage is not in use). A thin composition over the shared
// engine modules: one SpatialEngine + an environment grid + the
// cryptographic landscape layer. Its public API is unchanged, so
// SecurityMap3D keeps working exactly as before.

import { EnvironmentLayer } from "../../spatial/engine/EnvironmentLayer";
import { LandscapeLayer } from "../../spatial/engine/LandscapeLayer";
import { SpatialEngine } from "../../spatial/engine/SpatialEngine";

export class SecurityMapScene {
  constructor({ container, labelLayer, tooltip, onHover, onSelect, onContextLost, reducedMotion }) {
    this.engine = new SpatialEngine({ container, labelLayer, reducedMotion, onContextLost });
    this.environment = this.engine.addLayer(new EnvironmentLayer({ size: 30 }));
    this.landscape = this.engine.addLayer(
      new LandscapeLayer({
        tooltip,
        onHover,
        onSelect: (bomRef) => onSelect?.(bomRef),
        onClear: () => onSelect?.(null),
      }),
    );
  }

  setModel(model) {
    this.landscape.setModel(model);
    if (model) {
      this.environment.setSize(Math.max(model.bounds.width + 10, 30));
      this.fitAll({ animate: false });
    }
  }

  setState(state) {
    this.landscape.setState(state);
  }

  setReducedMotion(reducedMotion) {
    this.engine.setReducedMotion(reducedMotion);
  }

  fitAll({ animate = true } = {}) {
    this.engine.moveCamera(this.engine.frameFor(this.landscape.visiblePositions()), { animate });
  }

  resetView({ animate = true } = {}) {
    this.engine.moveCamera(this.engine.frameFor(this.landscape.allPositions()), { animate });
  }

  focusNode(ref, { animate = true } = {}) {
    const positions = this.landscape.focusPositions(ref);
    if (!positions.length) return;
    this.engine.moveCamera(this.engine.frameFor(positions, this.engine.currentDirection(), 5), { animate });
  }

  focusRegion(regionKey, { animate = true } = {}) {
    this.engine.moveCamera(this.engine.frameFor(this.landscape.regionPositions(regionKey)), { animate });
  }

  dispose() {
    this.engine.dispose();
  }
}
