// Cryptographic landscape layer: the Security Map content.
//
// Rendering only. It draws the display model built by securityMapModel.js
// (real ECDAT findings + recorded dependency edges) and reports hover /
// click back as bom_refs. Encoding is unchanged from the original map:
// region = cryptographic role, height/size = risk score, depth = migration
// priority, colour = risk severity, shape = migration strategy, edges =
// recorded CBOM dependencies. It never scores, filters or classifies.

import {
  BoxGeometry,
  BufferGeometry,
  Color,
  ConeGeometry,
  EdgesGeometry,
  Group,
  Line,
  LineBasicMaterial,
  LineDashedMaterial,
  LineSegments,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  OctahedronGeometry,
  PlaneGeometry,
  QuadraticBezierCurve3,
  Quaternion,
  RingGeometry,
  SphereGeometry,
  TorusGeometry,
  Vector3,
} from "three";

import { SEVERITY_COLORS, displayName, nodeRadius, shortRef } from "../../components/visualization/securityMapModel";
import { disposeObject } from "./SpatialEngine";

const CYAN = "#22d3ee";
const VIOLET = "#a78bfa";
const REVIEW = "#cbd5e1";
const EDGE_BASE = "#5b9cf6";
const EDGE_EMPHASIS = "#67e8f9";
const EMISSIVE_BY_SEVERITY = { CRITICAL: 0.6, HIGH: 0.42, MEDIUM: 0.2, LOW: 0.1, UNKNOWN: 0.08 };
const SEVERITY_BANDS = [
  { value: 30, label: "MEDIUM ≥ 30" },
  { value: 60, label: "HIGH ≥ 60" },
  { value: 80, label: "CRITICAL ≥ 80" },
];

export class LandscapeLayer {
  constructor({ onHover, onSelect, onClear, origin = new Vector3(0, 0, 0), tooltip = null, dimOthers = true } = {}) {
    this.group = new Group();
    this.group.position.copy(origin);
    this.onHover = onHover;
    this.onSelect = onSelect;
    this.onClear = onClear;
    this.tooltip = tooltip;
    this.dimOthers = dimOthers;
    this.pickPriority = 1;

    this.nodes = new Map();
    this.edges = [];
    this.regions = [];
    this.state = { focusedRef: null, visibleRefs: null, searchRefs: null, relatedRefs: new Set() };
    this.hoveredRef = null;
    this.emphasis = 1; // 0..1 — how present the whole landscape is (receded while investigating)
    this.pulseUntil = 0;

    const ringMaterial = new MeshBasicMaterial({ color: CYAN, transparent: true, opacity: 0.9, depthWrite: false });
    this.focusRing = new Mesh(new RingGeometry(1, 1.07, 64), ringMaterial);
    this.focusRing.visible = false;
    this.focusRing.renderOrder = 10;
    this.group.add(this.focusRing);

    this.content = new Group();
    this.group.add(this.content);
  }

  attach(engine) {
    this.engine = engine;
  }

  request() {
    this.engine?.requestFrame();
  }

  // ------------------------------------------------------------------
  // Model
  // ------------------------------------------------------------------

  setModel(model) {
    this.clearModel();
    this.model = model;
    if (!model) return;
    this.buildRegions(model);
    model.nodes.forEach((node) => this.buildNode(node));
    model.edges.forEach((edge) => this.buildEdge(edge));
    this.applyState(true);
  }

  clearModel() {
    [...this.content.children].forEach((child) => {
      this.content.remove(child);
      disposeObject(child);
    });
    this.engine?.removeLabels(this);
    this.nodes.clear();
    this.edges = [];
    this.regions = [];
    this.groupIndex = null;
  }

  label(options) {
    return this.engine.addLabel({ layer: this, ...options });
  }

  buildRegions(model) {
    const { height, depth } = model.bounds;
    const floorWidth = Math.max(model.bounds.width + 10, 30);

    model.regions.forEach((region) => {
      const plateWidth = Math.max(region.end - region.start + 0.8, 1.6);
      const plate = new Mesh(
        new PlaneGeometry(plateWidth, depth + 3),
        new MeshBasicMaterial({ color: "#0f1f3d", transparent: true, opacity: 0.42, depthWrite: false }),
      );
      plate.rotation.x = -Math.PI / 2;
      plate.position.set(region.center, 0.01, 0);
      this.content.add(plate);

      const outline = new LineSegments(
        new EdgesGeometry(plate.geometry),
        new LineBasicMaterial({ color: "#2e4a7a", transparent: true, opacity: 0.55 }),
      );
      outline.rotation.x = -Math.PI / 2;
      outline.position.copy(plate.position);
      this.content.add(outline);

      this.regions.push({ region, plate, outline });
      const label = this.label({
        className: "security-map-region-label",
        text: `${region.label} · ${region.count}`,
        position: new Vector3(region.center, 0.05, depth / 2 + 2.1),
        owner: this.group,
        collision: "row",
      });
      label.kind = "region";
    });

    const backZ = -depth / 2 - 1.8;
    const halfWidth = floorWidth / 2 - 2;
    SEVERITY_BANDS.forEach((band) => {
      const y = (band.value / 100) * height;
      const line = new Line(
        new BufferGeometry().setFromPoints([new Vector3(-halfWidth, y, backZ), new Vector3(halfWidth, y, backZ)]),
        new LineDashedMaterial({ color: "#3b5c94", dashSize: 0.5, gapSize: 0.35, transparent: true, opacity: 0.6 }),
      );
      line.computeLineDistances();
      this.content.add(line);
      const label = this.label({
        className: "security-map-band-label",
        text: band.label,
        position: new Vector3(-halfWidth, y + 0.25, backZ),
        owner: this.group,
        collision: null,
      });
      label.kind = "band";
    });
  }

  buildNode(node) {
    if (!node.position) return;

    const group = new Group();
    group.position.set(node.position.x, node.position.y, node.position.z);
    const radius = nodeRadius(node.riskScore);
    const color = new Color(SEVERITY_COLORS[node.riskSeverity] || SEVERITY_COLORS.UNKNOWN);
    const material = new MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: EMISSIVE_BY_SEVERITY[node.riskSeverity] ?? 0.1,
      roughness: 0.38,
      metalness: 0.18,
      transparent: true,
    });

    let geometry;
    if (node.strategy === "KEEP") geometry = new BoxGeometry(radius * 1.45, radius * 1.45, radius * 1.45);
    else if (node.strategy === "NEEDS_REVIEW") geometry = new OctahedronGeometry(radius * 1.3);
    else geometry = new SphereGeometry(radius, 32, 22);

    const body = new Mesh(geometry, material);
    group.add(body);

    const decorations = [];
    if (node.strategy === "DIRECT_PQC" || node.strategy === "HYBRID") {
      const ring = new Mesh(new TorusGeometry(radius * 1.55, 0.03, 8, 72), new MeshBasicMaterial({ color: CYAN, transparent: true }));
      ring.rotation.x = Math.PI / 2;
      group.add(ring);
      decorations.push(ring);
      if (node.strategy === "HYBRID") {
        const second = new Mesh(
          new TorusGeometry(radius * 1.55, 0.03, 8, 72),
          new MeshBasicMaterial({ color: VIOLET, transparent: true }),
        );
        second.rotation.set(Math.PI / 2 + 1.05, 0, 0.4);
        group.add(second);
        decorations.push(second);
      }
    } else if (node.strategy === "NEEDS_REVIEW") {
      const points = [];
      for (let i = 0; i <= 64; i += 1) {
        const angle = (i / 64) * Math.PI * 2;
        points.push(new Vector3(Math.cos(angle) * radius * 1.7, 0, Math.sin(angle) * radius * 1.7));
      }
      const dashed = new Line(
        new BufferGeometry().setFromPoints(points),
        new LineDashedMaterial({ color: REVIEW, dashSize: 0.12, gapSize: 0.1, transparent: true }),
      );
      dashed.computeLineDistances();
      group.add(dashed);
      decorations.push(dashed);
    } else if (node.strategy === "KEEP") {
      const edges = new LineSegments(new EdgesGeometry(geometry), new LineBasicMaterial({ color: "#94a3b8", transparent: true }));
      group.add(edges);
      decorations.push(edges);
    }

    const drop = new Line(
      new BufferGeometry().setFromPoints([new Vector3(0, 0, 0), new Vector3(0, -node.position.y, 0)]),
      new LineBasicMaterial({ color, transparent: true, opacity: 0.28 }),
    );
    group.add(drop);
    const marker = new Mesh(
      new RingGeometry(radius * 0.55, radius * 0.75, 32),
      new MeshBasicMaterial({ color, transparent: true, opacity: 0.35, depthWrite: false }),
    );
    marker.rotation.x = -Math.PI / 2;
    marker.position.y = -node.position.y + 0.03;
    group.add(marker);

    const hit = new Mesh(new SphereGeometry(Math.max(radius * 1.8, 0.62), 12, 8), new MeshBasicMaterial({ visible: false }));
    hit.userData = { id: node.bomRef, bomRef: node.bomRef };
    group.add(hit);

    this.content.add(group);

    const label = this.label({
      className: "security-map-node-label",
      text: displayName(node),
      position: new Vector3(0, radius + 0.55, 0),
      owner: group,
      collision: "box",
    });
    label.kind = "node";
    label.bomRef = node.bomRef;
    const refLine = document.createElement("span");
    refLine.className = "security-map-node-label-ref";
    refLine.textContent = shortRef(node.bomRef);
    label.element.dataset.bomRef = node.bomRef;
    label.element.appendChild(refLine);

    this.nodes.set(node.bomRef, {
      node,
      group,
      body,
      material,
      decorations,
      drop,
      marker,
      hit,
      label,
      radius,
      baseEmissive: material.emissiveIntensity,
      current: { scale: 1, opacity: 1 },
      target: { scale: 1, opacity: 1 },
    });
  }

  buildEdge(edge) {
    const from = this.nodes.get(edge.from);
    const to = this.nodes.get(edge.to);
    if (!from || !to) return;

    const start = from.group.position.clone();
    const end = to.group.position.clone();
    const mid = start.clone().lerp(end, 0.5);
    mid.y += Math.max(0.9, start.distanceTo(end) * 0.25);
    const curve = new QuadraticBezierCurve3(start, mid, end);

    const material = new LineBasicMaterial({ color: EDGE_BASE, transparent: true, opacity: 0.3, depthWrite: false });
    const line = new Line(new BufferGeometry().setFromPoints(curve.getPoints(28)), material);
    this.content.add(line);

    const t = MathUtils.clamp(1 - (to.radius * 1.9) / Math.max(curve.getLength(), 0.001), 0.5, 0.97);
    const arrowMaterial = new MeshBasicMaterial({ color: EDGE_BASE, transparent: true, opacity: 0.45, depthWrite: false });
    const arrow = new Mesh(new ConeGeometry(0.1, 0.3, 10), arrowMaterial);
    arrow.position.copy(curve.getPoint(t));
    arrow.quaternion.copy(new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), curve.getTangent(t).normalize()));
    this.content.add(arrow);

    this.edges.push({ edge, line, material, arrow, arrowMaterial, current: 0.3, target: 0.3, emphasized: false });
  }

  // ------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------

  setState({ focusedRef, visibleRefs, searchRefs, relatedRefs }) {
    if (focusedRef && focusedRef !== this.state.focusedRef) this.pulseUntil = performance.now() + 2600;
    this.state = { focusedRef, visibleRefs, searchRefs, relatedRefs: relatedRefs || new Set() };
    this.applyState(false);
  }

  /** 1 = full landscape, lower = receded behind an investigation. */
  setEmphasis(value) {
    if (this.emphasis === value) return;
    this.emphasis = value;
    this.applyState(false);
  }

  isVisible(ref) {
    return !this.state.visibleRefs || this.state.visibleRefs.has(ref);
  }

  applyState(immediate) {
    const { focusedRef, searchRefs, relatedRefs } = this.state;
    const unrelated = this.dimOthers ? 0.22 * Math.max(this.emphasis, 0.35) : 0.22;

    this.nodes.forEach((view, ref) => {
      const visible = this.isVisible(ref);
      let opacity = 1;
      if (focusedRef && ref !== focusedRef && !relatedRefs.has(ref)) opacity = unrelated;
      if (searchRefs && !searchRefs.has(ref) && ref !== focusedRef) opacity = Math.min(opacity, 0.22);
      let scale = ref === focusedRef ? 1.14 : 1;
      if (ref === this.hoveredRef) scale *= 1.16;
      view.target = { scale: visible ? scale : 0.001, opacity: visible ? opacity : 0 };
      if (immediate) view.current = { ...view.target };
    });

    this.edges.forEach((item) => {
      const { from, to } = item.edge;
      const visible = this.isVisible(from) && this.isVisible(to);
      const chain = focusedRef && (from === focusedRef || to === focusedRef || (relatedRefs.has(from) && relatedRefs.has(to)));
      item.emphasized = Boolean(chain);
      item.target = !visible ? 0 : focusedRef ? (chain ? 0.95 : 0.06) : searchRefs ? 0.14 : 0.3;
      if (immediate) item.current = item.target;
      const color = item.emphasized ? EDGE_EMPHASIS : EDGE_BASE;
      item.material.color.set(color);
      item.arrowMaterial.color.set(color);
    });

    const plateOpacity = 0.42 * (0.45 + 0.55 * this.emphasis);
    this.regions.forEach(({ plate, outline }) => {
      plate.material.opacity = plateOpacity;
      outline.material.opacity = 0.55 * (0.45 + 0.55 * this.emphasis);
    });

    this.request();
  }

  // ------------------------------------------------------------------
  // Geometry queries (for camera framing)
  // ------------------------------------------------------------------

  worldPosition(view) {
    return view.group.getWorldPosition(new Vector3());
  }

  nodeWorldPosition(ref) {
    const view = this.nodes.get(ref);
    return view ? this.worldPosition(view) : null;
  }

  visiblePositions() {
    const positions = [];
    this.nodes.forEach((view, ref) => {
      if (this.isVisible(ref)) positions.push(this.worldPosition(view));
    });
    if (!positions.length) this.nodes.forEach((view) => positions.push(this.worldPosition(view)));
    return positions;
  }

  allPositions() {
    return [...this.nodes.values()].map((view) => this.worldPosition(view));
  }

  focusPositions(ref) {
    const view = this.nodes.get(ref);
    if (!view) return [];
    const related = [...this.state.relatedRefs]
      .map((relatedRef) => this.nodes.get(relatedRef))
      .filter((item) => item && this.isVisible(item.node.bomRef))
      .map((item) => this.worldPosition(item));
    return [this.worldPosition(view), ...related];
  }

  regionPositions(regionKey) {
    const positions = [];
    this.nodes.forEach((view, ref) => {
      if (view.node.regionKey === regionKey && this.isVisible(ref)) positions.push(this.worldPosition(view));
    });
    return positions;
  }

  // ------------------------------------------------------------------
  // Picking
  // ------------------------------------------------------------------

  pickTargets() {
    const targets = [];
    this.nodes.forEach((view, ref) => {
      if (this.isVisible(ref) && view.current.opacity > 0.05) targets.push(view.hit);
    });
    return targets;
  }

  setHovered(target) {
    const ref = target?.bomRef || null;
    if (ref === this.hoveredRef) return;
    this.hoveredRef = ref;
    this.onHover?.(ref);
    this.applyState(false);
  }

  onPick(target) {
    this.onSelect?.(target.bomRef);
  }

  onPickNothing() {
    this.onClear?.();
  }

  // ------------------------------------------------------------------
  // Frame
  // ------------------------------------------------------------------

  update({ now, blend, reducedMotion, camera }) {
    let active = false;

    this.nodes.forEach((view) => {
      const { current, target } = view;
      current.scale += (target.scale - current.scale) * blend;
      current.opacity += (target.opacity - current.opacity) * blend;
      if (Math.abs(target.scale - current.scale) > 0.002 || Math.abs(target.opacity - current.opacity) > 0.004) active = true;
      else {
        current.scale = target.scale;
        current.opacity = target.opacity;
      }
      view.group.visible = current.opacity > 0.01 && current.scale > 0.01;
      view.body.scale.setScalar(current.scale);
      view.decorations.forEach((decoration) => {
        decoration.scale.setScalar(current.scale);
        decoration.material.opacity = current.opacity;
      });
      view.material.opacity = current.opacity;
      view.material.emissiveIntensity = view.baseEmissive * (0.4 + 0.6 * current.opacity);
      view.drop.material.opacity = 0.28 * current.opacity;
      view.marker.material.opacity = 0.35 * current.opacity;
    });

    this.edges.forEach((item) => {
      item.current += (item.target - item.current) * blend;
      if (Math.abs(item.target - item.current) > 0.004) active = true;
      else item.current = item.target;
      item.material.opacity = item.current;
      item.arrowMaterial.opacity = Math.min(1, item.current * 1.3);
      item.line.visible = item.current > 0.01;
      item.arrow.visible = item.current > 0.01;
    });

    // Focus ring: billboard around the focused node; pulses briefly after
    // a new focus, then holds still so the loop can stop.
    const focused = this.state.focusedRef ? this.nodes.get(this.state.focusedRef) : null;
    if (focused && focused.group.visible) {
      this.focusRing.visible = true;
      this.focusRing.position.copy(focused.group.position);
      this.focusRing.lookAt(camera.position);
      const pulsing = !reducedMotion && now < this.pulseUntil;
      const pulse = pulsing ? 1 + Math.sin(now / 420) * 0.06 : 1;
      this.focusRing.scale.setScalar(focused.radius * 2.25 * pulse * focused.current.scale);
      if (pulsing) active = true;
      else if (this.pulseUntil) {
        this.pulseUntil = 0;
        active = true;
      }
    } else {
      this.focusRing.visible = false;
    }

    return active;
  }

  // ------------------------------------------------------------------
  // Labels
  // ------------------------------------------------------------------

  labelState(label) {
    if (!this.group.visible) return { show: false };
    const { focusedRef, relatedRefs, searchRefs } = this.state;
    if (label.kind === "region") return { show: this.emphasis > 0.5, priority: 2 };
    if (label.kind === "band") return { show: this.emphasis > 0.5, priority: 3 };

    const view = this.nodes.get(label.bomRef);
    const ref = label.bomRef;
    let show = Boolean(view && view.group.visible && view.current.opacity > 0.5);
    if (show) {
      if (focusedRef) show = ref === focusedRef || ref === this.hoveredRef || relatedRefs.has(ref);
      else if (searchRefs) show = searchRefs.has(ref) || ref === this.hoveredRef;
      else show = ref === this.hoveredRef || (this.emphasis > 0.5 && ["HIGH", "CRITICAL"].includes(view.node.priorityLevel));
    }
    const emphasis = ref === focusedRef || ref === this.hoveredRef;
    return { show, emphasis, priority: emphasis ? 0 : 1 };
  }

  afterLabels(project) {
    if (!this.tooltip) return;
    const hovered = this.hoveredRef ? this.nodes.get(this.hoveredRef) : null;
    if (!hovered || !hovered.group.visible) return;
    const { x, y, width } = project(this.worldPosition(hovered));
    const flip = x > width - 220;
    this.tooltip.style.transform = `translate(${(x + (flip ? -16 : 16)).toFixed(1)}px, ${(y - 12).toFixed(1)}px) translateX(${flip ? "-100%" : "0"})`;
  }

  dispose() {
    this.clearModel();
  }
}
