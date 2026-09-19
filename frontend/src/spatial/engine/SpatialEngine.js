// The single shared three.js engine for ECDAT.
//
// It owns exactly one WebGLRenderer / canvas, one scene, one camera and
// one OrbitControls, plus the on-demand render loop, picking, the DOM
// label layer and camera framing. Everything that is drawn lives in
// layers (environment, posture, landscape, investigation, simulation)
// that plug into this engine. The engine renders only while something
// is changing, and never while the tab is hidden, the canvas is
// off-screen, or the engine is paused.

import {
  AmbientLight,
  DirectionalLight,
  FogExp2,
  HemisphereLight,
  MathUtils,
  PerspectiveCamera,
  Raycaster,
  Scene,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

import { paintThemed, paintThemedGrid, refreshPalette } from "./themePalette.js";

export const DEFAULT_DIRECTION = new Vector3(0.62, 0.5, 1).normalize();

export function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

export function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose?.();
    const materials = Array.isArray(child.material) ? child.material : child.material ? [child.material] : [];
    materials.forEach((material) => material.dispose());
  });
}

export class SpatialEngine {
  constructor({
    container,
    labelLayer,
    reducedMotion = false,
    onContextLost,
    canvasClassName = "security-map-canvas",
    pixelRatioCap = 2,
    maxDistance = 90,
  }) {
    this.container = container;
    this.labelLayer = labelLayer;
    this.onContextLost = onContextLost;
    this.reducedMotion = Boolean(reducedMotion);

    this.layers = [];
    this.labels = [];
    this.pointer = new Vector2();
    this.pointerInside = false;
    this.pointerDirty = false;
    this.downPoint = null;
    this.hovered = null; // { layer, target }
    this.tween = null;
    this.needsRender = true;
    this.inView = true;
    this.paused = false;
    this.insets = { left: 0, right: 0, top: 0, bottom: 0 };
    this.lastTime = performance.now();
    this.disposed = false;

    this.renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, pixelRatioCap));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.domElement.className = canvasClassName;
    this.renderer.domElement.setAttribute("aria-hidden", "true");
    container.appendChild(this.renderer.domElement);

    this.scene = new Scene();
    this.scene.fog = new FogExp2("#05070f", 0.016);

    this.camera = new PerspectiveCamera(42, 1, 0.1, 500);
    this.camera.position.set(4, 16, 30);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = !this.reducedMotion;
    this.controls.dampingFactor = 0.09;
    this.controls.minDistance = 4;
    this.controls.maxDistance = maxDistance;
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.screenSpacePanning = true;
    this.controls.addEventListener("change", () => {
      this.needsRender = true;
    });
    this.controls.addEventListener("start", () => {
      this.tween = null;
    });

    this.hemiLight = new HemisphereLight("#a5b8ff", "#05070f", 0.85);
    this.scene.add(this.hemiLight);
    this.ambientLight = new AmbientLight("#1e293b", 0.6);
    this.scene.add(this.ambientLight);
    const key = new DirectionalLight("#ffffff", 1.35);
    key.position.set(10, 18, 14);
    this.scene.add(key);
    this.keyLight = key;
    const rim = new DirectionalLight("#22d3ee", 0.35);
    rim.position.set(-14, 6, -12);
    this.scene.add(rim);
    this.rimLight = rim;


    this.raycaster = new Raycaster();

    this.handlePointerMove = this.handlePointerMove.bind(this);
    this.handlePointerLeave = this.handlePointerLeave.bind(this);
    this.handlePointerDown = this.handlePointerDown.bind(this);
    this.handlePointerUp = this.handlePointerUp.bind(this);
    this.handleContextLost = this.handleContextLost.bind(this);
    this.handleVisibility = this.handleVisibility.bind(this);
    this.frame = this.frame.bind(this);

    // Paint the environment for the current theme. Done last: applyTheme
    // requests a frame, which needs the bound frame loop above.
    this.applyTheme();

    const canvas = this.renderer.domElement;
    canvas.addEventListener("pointermove", this.handlePointerMove);
    canvas.addEventListener("pointerleave", this.handlePointerLeave);
    canvas.addEventListener("pointerdown", this.handlePointerDown);
    canvas.addEventListener("pointerup", this.handlePointerUp);
    canvas.addEventListener("webglcontextlost", this.handleContextLost);
    document.addEventListener("visibilitychange", this.handleVisibility);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);

    this.intersectionObserver = new IntersectionObserver((entries) => {
      this.inView = entries.some((entry) => entry.isIntersecting);
      if (this.inView) this.requestFrame();
    });
    this.intersectionObserver.observe(container);

    this.resize();
    this.requestFrame();
  }

  // ------------------------------------------------------------------
  // Layers
  // ------------------------------------------------------------------

  addLayer(layer) {
    this.layers.push(layer);
    if (layer.group) this.scene.add(layer.group);
    layer.attach?.(this);
    this.requestFrame();
    return layer;
  }

  /**
   * Adds a projected DOM label. `layer.labelState(label)` decides each
   * frame whether it shows; `collision` is "row" (one-dimensional, used for
   * region names) or "box" (node / anchor labels); `priority` orders
   * placement so emphasised labels always win.
   */
  addLabel({ layer, className, text, position, owner = null, collision = "box" }) {
    const element = document.createElement("div");
    element.className = className;
    element.textContent = text;
    this.labelLayer?.appendChild(element);
    const label = { layer, element, position, owner, collision, visible: true };
    this.labels.push(label);
    return label;
  }

  removeLabels(layer) {
    this.labels = this.labels.filter((label) => {
      if (label.layer !== layer) return true;
      label.element.remove();
      return false;
    });
  }

  setReducedMotion(reducedMotion) {
    this.reducedMotion = Boolean(reducedMotion);
    this.controls.enableDamping = !this.reducedMotion;
    this.layers.forEach((layer) => layer.setReducedMotion?.(this.reducedMotion));
    this.requestFrame();
  }

  setPaused(paused) {
    this.paused = Boolean(paused);
    if (!this.paused) this.requestFrame();
  }

  // ------------------------------------------------------------------
  // Viewport insets (docked HTML panels)
  // ------------------------------------------------------------------

  /** Pixels of the canvas covered by docked panels; the view recentres into the rest. */
  setInsets(insets) {
    const next = { left: 0, right: 0, top: 0, bottom: 0, ...insets };
    const same = ["left", "right", "top", "bottom"].every((key) => Math.round(next[key]) === Math.round(this.insets[key]));
    this.insets = next;
    if (!same) this.resize();
  }

  // ------------------------------------------------------------------
  // Camera
  // ------------------------------------------------------------------

  /**
   * Camera frame (position + target) that fits `positions` into the part of
   * the canvas not covered by docks, seen from `direction`.
   */
  frameFor(positions, direction = DEFAULT_DIRECTION, minRadius = 2, { lift = 1.2, fill = 0.84 } = {}) {
    if (!positions.length) return null;

    const min = new Vector3(Infinity, Infinity, Infinity);
    const max = new Vector3(-Infinity, -Infinity, -Infinity);
    positions.forEach((position) => {
      min.min(position);
      max.max(position);
    });
    min.y = Math.min(min.y, 0);
    const center = min.clone().add(max).multiplyScalar(0.5);
    const pad = new Vector3(minRadius, 0, minRadius).sub(max.clone().sub(min).multiplyScalar(0.5)).max(new Vector3());
    min.sub(pad).sub(new Vector3(0.9, 0, 0.9));
    max.add(pad).add(new Vector3(0.9, 1.1, 0.9));
    center.copy(min).add(max).multiplyScalar(0.5);

    const corners = [];
    positions.forEach((position) => {
      corners.push(position.clone().add(new Vector3(0, lift, 0)), new Vector3(position.x, Math.min(0, position.y), position.z));
    });
    if (pad.lengthSq() > 0) {
      [min.x, max.x].forEach((x) => [min.z, max.z].forEach((z) => corners.push(new Vector3(x, center.y, z))));
    }

    const { width, height } = this.size();
    const effWidth = Math.max(width - this.insets.left - this.insets.right, 1);
    const effHeight = Math.max(height - this.insets.top - this.insets.bottom, 1);
    const fillX = fill * (effWidth / width);
    const fillY = fill * (effHeight / height);

    const probe = this.camera.clone();
    probe.clearViewOffset();
    probe.aspect = width / height;
    probe.updateProjectionMatrix();

    const unit = direction.clone().normalize();
    const target = center.clone();
    const right = new Vector3();
    const up = new Vector3();
    const projected = new Vector3();
    const halfTan = Math.tan(MathUtils.degToRad(probe.fov) / 2);
    let distance = Math.max(center.distanceTo(max), minRadius) * 2.4;
    for (let pass = 0; pass < 14; pass += 1) {
      probe.position.copy(target).addScaledVector(unit, distance);
      probe.lookAt(target);
      probe.updateMatrixWorld();
      let minX = Infinity;
      let maxX = -Infinity;
      let minY = Infinity;
      let maxY = -Infinity;
      let behind = false;
      corners.forEach((corner) => {
        projected.copy(corner).project(probe);
        if (projected.z >= 1) behind = true;
        minX = Math.min(minX, projected.x);
        maxX = Math.max(maxX, projected.x);
        minY = Math.min(minY, projected.y);
        maxY = Math.max(maxY, projected.y);
      });
      if (behind) {
        distance *= 1.6;
        continue;
      }
      right.setFromMatrixColumn(probe.matrixWorld, 0);
      up.setFromMatrixColumn(probe.matrixWorld, 1);
      const halfHeight = halfTan * distance;
      target.addScaledVector(right, ((minX + maxX) / 2) * halfHeight * probe.aspect * 0.8);
      target.addScaledVector(up, ((minY + maxY) / 2) * halfHeight * 0.8);
      const ratio = Math.max((maxX - minX) / 2 / fillX, (maxY - minY) / 2 / fillY);
      if (!ratio) break;
      distance *= 0.5 + ratio * 0.5;
    }
    distance = MathUtils.clamp(distance, this.controls.minDistance, this.controls.maxDistance);
    return { target, position: target.clone().addScaledVector(unit, distance) };
  }

  /** The current viewing direction (target → camera), kept above the floor. */
  currentDirection(minY = 0.25) {
    const direction = this.camera.position.clone().sub(this.controls.target);
    if (direction.lengthSq() < 0.001) direction.copy(DEFAULT_DIRECTION);
    direction.normalize();
    if (direction.y < minY) direction.y = minY;
    return direction.normalize();
  }

  moveCamera(frame, { animate = true, duration = 750 } = {}) {
    if (!frame) return;
    if (!animate || this.reducedMotion) {
      this.tween = null;
      this.camera.position.copy(frame.position);
      this.controls.target.copy(frame.target);
      this.controls.update();
      this.requestFrame();
      return;
    }
    this.tween = {
      start: performance.now(),
      duration,
      fromPosition: this.camera.position.clone(),
      toPosition: frame.position,
      fromTarget: this.controls.target.clone(),
      toTarget: frame.target,
    };
    this.requestFrame();
  }

  // ------------------------------------------------------------------
  // Pointer / picking
  // ------------------------------------------------------------------

  updatePointer(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  }

  pick() {
    this.raycaster.setFromCamera(this.pointer, this.camera);
    let best = null;
    this.layers.forEach((layer) => {
      const targets = layer.pickTargets?.() || [];
      if (!targets.length) return;
      const hit = this.raycaster.intersectObjects(targets, false)[0];
      if (!hit) return;
      const priority = layer.pickPriority ?? 0;
      if (!best || priority > best.priority || (priority === best.priority && hit.distance < best.distance)) {
        best = { layer, target: hit.object.userData, distance: hit.distance, priority };
      }
    });
    return best;
  }

  setHovered(hit) {
    const previous = this.hovered;
    const same =
      (previous === null && hit === null) ||
      (previous && hit && previous.layer === hit.layer && previous.target.id === hit.target.id);
    if (same) return;
    if (previous && (!hit || previous.layer !== hit.layer)) previous.layer.setHovered?.(null);
    this.hovered = hit;
    if (hit) hit.layer.setHovered?.(hit.target);
    this.renderer.domElement.style.cursor = hit ? "pointer" : "grab";
    this.requestFrame();
  }

  handlePointerMove(event) {
    if (event.pointerType === "touch") return;
    this.updatePointer(event);
    this.pointerInside = true;
    this.pointerDirty = true;
    this.requestFrame();
  }

  handlePointerLeave() {
    this.pointerInside = false;
    this.setHovered(null);
  }

  handlePointerDown(event) {
    this.downPoint = { x: event.clientX, y: event.clientY };
  }

  handlePointerUp(event) {
    if (!this.downPoint) return;
    const moved = Math.hypot(event.clientX - this.downPoint.x, event.clientY - this.downPoint.y);
    this.downPoint = null;
    if (moved > 6) return;
    this.updatePointer(event);
    const hit = this.pick();
    if (hit) hit.layer.onPick?.(hit.target);
    else this.layers.forEach((layer) => layer.onPickNothing?.());
  }

  handleContextLost(event) {
    event.preventDefault();
    this.onContextLost?.();
  }

  handleVisibility() {
    if (!document.hidden) this.requestFrame();
  }

  // ------------------------------------------------------------------
  // Loop
  // ------------------------------------------------------------------

  size() {
    return {
      width: Math.max(this.container.clientWidth, 1),
      height: Math.max(this.container.clientHeight, 1),
    };
  }

  resize() {
    const { width, height } = this.size();
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    const { left, right, top, bottom } = this.insets;
    if (left || right || top || bottom) {
      // Shift the principal point so the scene centres in the uncovered area.
      this.camera.setViewOffset(width, height, (right - left) / 2, (bottom - top) / 2, width, height);
    } else {
      this.camera.clearViewOffset();
    }
    this.camera.updateProjectionMatrix();
    this.requestFrame();
  }

  requestFrame() {
    this.needsRender = true;
    if (this.rafId || this.disposed) return;
    this.rafId = requestAnimationFrame(this.frame);
  }

  frame(now) {
    this.rafId = null;
    if (this.disposed) return;
    const delta = Math.min((now - this.lastTime) / 1000, 0.1);
    this.lastTime = now;

    if (!this.inView || document.hidden || this.paused) return;

    let active = false;

    if (this.tween) {
      const t = Math.min((now - this.tween.start) / this.tween.duration, 1);
      const eased = easeInOutCubic(t);
      this.camera.position.lerpVectors(this.tween.fromPosition, this.tween.toPosition, eased);
      this.controls.target.lerpVectors(this.tween.fromTarget, this.tween.toTarget, eased);
      if (t >= 1) this.tween = null;
      active = true;
    }

    if (this.controls.update()) active = true;

    if (this.pointerDirty && this.pointerInside) {
      this.pointerDirty = false;
      this.setHovered(this.pick());
    }

    const blend = this.reducedMotion ? 1 : 1 - Math.exp(-delta * 11);
    this.layers.forEach((layer) => {
      if (layer.update?.({ now, delta, blend, reducedMotion: this.reducedMotion, camera: this.camera })) active = true;
    });

    if (active || this.needsRender) {
      this.renderer.render(this.scene, this.camera);
      this.updateLabels();
      this.needsRender = false;
    }

    if (active) this.rafId = requestAnimationFrame(this.frame);
  }

  updateLabels() {
    if (!this.labelLayer) return;
    const { width, height } = this.size();
    const projected = new Vector3();
    const rows = [];
    const boxes = [];

    const states = this.labels.map((label) => ({ label, state: label.layer.labelState?.(label) || { show: true } }));
    states.sort((a, b) => (a.state.priority ?? 1) - (b.state.priority ?? 1));

    states.forEach(({ label, state }) => {
      const emphasis = Boolean(state.emphasis);
      if (label.owner) projected.copy(label.position).applyMatrix4(label.owner.matrixWorld);
      else projected.copy(label.position);
      projected.project(this.camera);
      const behind = projected.z > 1 || projected.z < -1;
      const x = (projected.x * 0.5 + 0.5) * width;
      const y = (-projected.y * 0.5 + 0.5) * height;
      const outside =
        x < this.insets.left - 40 || x > width - this.insets.right + 40 || y < this.insets.top - 20 || y > height - this.insets.bottom + 20;

      let visible = Boolean(state.show) && !behind && !outside;

      if (visible && label.collision === "row" && !emphasis) {
        if (!label.width) label.width = label.element.offsetWidth || label.element.textContent.length * 7;
        const left = x - label.width / 2 - 6;
        const right = x + label.width / 2 + 6;
        if (left < this.insets.left || right > width - this.insets.right || rows.some(([a, b]) => left < b && right > a)) visible = false;
        else rows.push([left, right]);
      } else if (visible && label.collision === "box") {
        if (!label.width) {
          label.width = label.element.offsetWidth || label.element.textContent.length * 7;
          label.height = label.element.offsetHeight || 20;
        }
        const box = [x - label.width / 2, y - label.height, x + label.width / 2, y];
        const overlaps = boxes.some((other) => box[0] < other[2] && box[2] > other[0] && box[1] < other[3] && box[3] > other[1]);
        if (overlaps && !emphasis) visible = false;
        else boxes.push(box);
      }

      if (visible !== label.visible) {
        label.element.style.display = visible ? "" : "none";
        label.visible = visible;
      }
      if (visible) {
        label.element.style.transform = `translate(-50%, -100%) translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
        label.element.classList.toggle("is-emphasis", emphasis);
      }
    });

    this.layers.forEach((layer) => layer.afterLabels?.((position) => {
      projected.copy(position).project(this.camera);
      return { x: (projected.x * 0.5 + 0.5) * width, y: (-projected.y * 0.5 + 0.5) * height, width, height };
    }));
  }

  /**
   * Repaints the environment for the current theme: fog, lighting and
   * every registered environment material. One renderer, one scene --
   * only the colours change, so camera, layers and picking are untouched.
   */
  applyTheme() {
    const palette = refreshPalette();
    this.palette = palette;

    if (this.scene.fog) {
      this.scene.fog.color.set(palette.fog);
      // Fog pulls geometry toward its own colour. Against a near-black
      // fog that deepens the scene, but against a pale one it drains the
      // severity colours -- which are the one thing here that has to stay
      // readable -- so daylight uses a much thinner fog.
      this.scene.fog.density = palette.fogDensity;
    }

    if (this.hemiLight) {
      this.hemiLight.color.set(palette.sky);
      this.hemiLight.groundColor.set(palette.ground);
      this.hemiLight.intensity = 0.85 * palette.lightIntensity;
    }
    if (this.ambientLight) {
      this.ambientLight.intensity = 0.6 * palette.lightIntensity;
      // In daylight the ambient fill has to be neutral, or every surface
      // picks up the dark theme's navy cast.
      this.ambientLight.color.set(palette.theme === "light" ? "#dbe6f7" : "#1e293b");
    }
    if (this.keyLight) this.keyLight.intensity = 1.35 * palette.lightIntensity;
    if (this.rimLight) this.rimLight.intensity = 0.35 * palette.glowIntensity;

    // Whatever is in the scene right now is exactly the live set, so a
    // rebuilt layer never leaves a stale material behind and nothing has
    // to keep a registry pruned.
    this.scene.traverse((object) => {
      paintThemedGrid(object, palette);
      const material = object.material;
      if (!material) return;
      if (Array.isArray(material)) {
        material.forEach((entry) => paintThemed(entry, palette));
      } else {
        paintThemed(material, palette);
      }
    });

    this.needsRender = true;
    this.requestFrame?.();
  }

  dispose() {
    this.disposed = true;
    if (this.rafId) cancelAnimationFrame(this.rafId);
    const canvas = this.renderer.domElement;
    canvas.removeEventListener("pointermove", this.handlePointerMove);
    canvas.removeEventListener("pointerleave", this.handlePointerLeave);
    canvas.removeEventListener("pointerdown", this.handlePointerDown);
    canvas.removeEventListener("pointerup", this.handlePointerUp);
    canvas.removeEventListener("webglcontextlost", this.handleContextLost);
    document.removeEventListener("visibilitychange", this.handleVisibility);
    this.resizeObserver.disconnect();
    this.intersectionObserver.disconnect();
    this.controls.dispose();
    this.layers.forEach((layer) => {
      layer.dispose?.();
      if (layer.group) {
        this.scene.remove(layer.group);
        disposeObject(layer.group);
      }
    });
    this.labels.forEach((label) => label.element.remove());
    this.labels = [];
    this.layers = [];
    this.renderer.dispose();
    canvas.remove();
  }
}
