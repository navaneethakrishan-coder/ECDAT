// Investigation space around the selected finding.
//
// The finding's node in the landscape is the anchor. Around it:
//  - six analysis-surface anchors (Evidence, Risk, Blast Radius, Migration,
//    What-If, AI Analysis) joined to the node, mirroring the HTML hub;
//  - the active surface's own geometry, drawn only from real data:
//      risk      a gauge at the node's risk height with the severity bands
//      blast     halos on the node's recorded dependencies / dependents
//      migration the strategy's stages (migrationStages) as a path
//      evidence  the evidence chain's step statuses from /api/evidence
// Nothing here scores, infers or connects findings on its own.

import {
  BufferGeometry,
  Color,
  Group,
  Line,
  LineBasicMaterial,
  LineDashedMaterial,
  Mesh,
  MeshBasicMaterial,
  OctahedronGeometry,
  PlaneGeometry,
  RingGeometry,
  Vector3,
} from "three";

import { INVESTIGATION_SURFACES } from "../surfaces";
import { disposeObject } from "./SpatialEngine";

const TONE_HEX = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
  pqc: "#22d3ee",
  review: "#f97316",
  simulation: "#a78bfa",
  ai: "#a78bfa",
  neutral: "#5b9cf6",
  unknown: "#64748b",
};

const STAGE_HEX = { current: "#94a3b8", pqc: "#22d3ee", hybrid: "#a78bfa", retain: "#64748b", review: "#f97316" };
const CHAIN_HEX = {
  established: "#22d3ee",
  "low-confidence": "#eab308",
  unresolved: "#f97316",
  unknown: "#64748b",
  "not-applicable": "#475569",
};
const CHAIN_LABEL = {
  established: "Established",
  "low-confidence": "Low confidence",
  unresolved: "Unresolved",
  unknown: "Unknown",
  "not-applicable": "Not applicable",
};
const BANDS = [30, 60, 80];

// The direction the camera looks at an investigation from (target → camera).
export const INVESTIGATION_DIRECTION = new Vector3(0.45, 0.55, 1).normalize();

export class InvestigationLayer {
  constructor({ landscape, onSurface } = {}) {
    this.group = new Group();
    this.landscape = landscape;
    this.onSurface = onSurface;
    this.pickPriority = 3;
    this.anchors = new Map();
    this.extras = new Group();
    this.anchorGroup = new Group();
    this.group.add(this.anchorGroup);
    this.group.add(this.extras);
    this.focus = null;
    this.hoveredKey = null;
    this.surfacePoints = [];
  }

  attach(engine) {
    this.engine = engine;
  }

  /**
   * focus = { bomRef, activeSurface, summaries, stages, evidenceSteps, heightScale } | null
   * Rebuilds only when the bom_ref, surface or the data behind it changes.
   */
  setFocus(focus) {
    const view = focus ? this.landscape.nodes.get(focus.bomRef) : null;
    if (!focus || !view) {
      this.clear();
      this.focus = null;
      this.engine?.requestFrame();
      return;
    }
    const signature = [
      focus.bomRef,
      focus.activeSurface,
      JSON.stringify(focus.summaries),
      JSON.stringify(focus.stages),
      JSON.stringify(focus.evidenceSteps),
    ].join("|");
    if (signature === this.signature) return;
    this.signature = signature;
    this.focus = focus;
    this.clear(false);
    this.view = view;
    this.group.position.copy(this.landscape.worldPosition(view));
    this.buildAnchors(focus, view);
    this.buildExtras(focus, view);
    this.engine?.requestFrame();
  }

  clear(resetSignature = true) {
    [this.anchorGroup, this.extras].forEach((container) => {
      [...container.children].forEach((child) => {
        container.remove(child);
        disposeObject(child);
      });
    });
    this.engine?.removeLabels(this);
    this.anchors.clear();
    this.surfacePoints = [];
    if (resetSignature) this.signature = null;
  }

  label(className, text, position, extra = {}) {
    const label = this.engine.addLabel({ layer: this, className, text, position, owner: this.group, collision: "box" });
    Object.assign(label, extra);
    return label;
  }

  buildAnchors(focus, view) {
    // Two rows of three on a plane facing the investigation camera, just
    // behind and above the node: no anchor hides another from that view.
    const forward = INVESTIGATION_DIRECTION.clone();
    const right = new Vector3(0, 1, 0).cross(forward).normalize();
    const lift = Math.max(2.4, view.radius + 2);
    INVESTIGATION_SURFACES.forEach((surface, index) => {
      const column = (index % 3) - 1;
      const row = index < 3 ? 1 : 0;
      const position = right
        .clone()
        .multiplyScalar(column * 4.4)
        .add(new Vector3(0, lift + row * 1.9, 0))
        .addScaledVector(forward, -1.4);
      const summary = focus.summaries?.[surface.key];
      const active = focus.activeSurface === surface.key;
      const color = new Color(TONE_HEX[summary?.tone] || TONE_HEX.neutral);

      // The HTML label is the anchor's visible face; this plate is its
      // (invisible) pick target in the 3D world, and a small node marks
      // where the connector lands.
      const plate = new Mesh(new PlaneGeometry(1.9, 0.7), new MeshBasicMaterial({ visible: false }));
      plate.position.copy(position);
      plate.userData = { id: surface.key, surface: surface.key };
      this.anchorGroup.add(plate);

      const outline = new Mesh(
        new RingGeometry(0.07, 0.12, 20),
        new MeshBasicMaterial({ color: active ? "#67e8f9" : color, transparent: true, opacity: active ? 1 : 0.8, depthWrite: false }),
      );
      outline.position.copy(position);
      outline.userData.billboard = true;
      this.extras.add(outline);

      const connector = new Line(
        new BufferGeometry().setFromPoints([new Vector3(0, view.radius * 0.9, 0), position]),
        active
          ? new LineBasicMaterial({ color: "#22d3ee", transparent: true, opacity: 0.95 })
          : new LineDashedMaterial({ color: "#5b9cf6", dashSize: 0.18, gapSize: 0.14, transparent: true, opacity: 0.55 }),
      );
      connector.computeLineDistances?.();
      this.anchorGroup.add(connector);

      const labelPosition = position.clone().add(new Vector3(0, 0.62, 0));
      const label = this.label(
        `stage-anchor-label${active ? " is-active" : ""}`,
        surface.label,
        labelPosition,
        { kind: "anchor", key: surface.key },
      );
      if (summary?.value) {
        const value = document.createElement("span");
        value.className = `stage-anchor-value tone-${summary.tone}`;
        value.textContent = summary.value;
        label.element.appendChild(value);
      }
      label.element.dataset.surface = surface.key;

      this.anchors.set(surface.key, { plate, outline, connector, position, label });
      this.surfacePoints.push(this.group.position.clone().add(position));
    });
  }

  buildExtras(focus, view) {
    switch (focus.activeSurface) {
      case "risk":
        this.buildRiskGauge(focus, view);
        break;
      case "blast":
        this.buildBlast(view);
        break;
      case "migration":
        this.buildMigration(focus, view);
        break;
      case "evidence":
        this.buildEvidence(focus, view);
        break;
      default:
        break;
    }
  }

  buildRiskGauge(focus, view) {
    const height = focus.heightScale;
    const nodeY = view.node.position.y;
    const x = -view.radius - 1.1;
    // Column from the floor to the top of the risk scale, in node-local space.
    const column = new Line(
      new BufferGeometry().setFromPoints([new Vector3(x, -nodeY, 0), new Vector3(x, height - nodeY, 0)]),
      new LineBasicMaterial({ color: "#2e4066", transparent: true, opacity: 0.9 }),
    );
    this.extras.add(column);
    BANDS.forEach((band) => {
      const y = (band / 100) * height - nodeY;
      const tick = new Line(
        new BufferGeometry().setFromPoints([new Vector3(x - 0.25, y, 0), new Vector3(x + 0.25, y, 0)]),
        new LineBasicMaterial({ color: "#3b5c94", transparent: true, opacity: 0.9 }),
      );
      this.extras.add(tick);
    });
    const marker = new Mesh(
      new RingGeometry(0.16, 0.26, 24),
      new MeshBasicMaterial({ color: TONE_HEX[String(view.node.riskSeverity).toLowerCase()] || "#22d3ee", transparent: true }),
    );
    marker.position.set(x, 0, 0);
    this.extras.add(marker);
    this.label(
      "stage-path-label",
      `Risk ${typeof view.node.riskScore === "number" ? view.node.riskScore.toFixed(2) : "—"} · ${view.node.riskSeverity}`,
      new Vector3(x - 0.1, 0.35, 0),
      { kind: "extra" },
    );
    this.surfacePoints.push(this.group.position.clone().add(new Vector3(x, height - nodeY, 0)));
  }

  buildBlast(view) {
    const node = view.node;
    const origin = this.group.position;
    const tiers = [
      { refs: node.dependencies, color: "#94a3b8", label: "Depends on" },
      { refs: node.directDependents, color: "#22d3ee", label: "Direct dependent" },
      { refs: node.transitiveDependents.filter((ref) => !node.directDependents.includes(ref)), color: "#a78bfa", label: "Indirect dependent" },
    ];
    tiers.forEach((tier) => {
      tier.refs.forEach((ref) => {
        const target = this.landscape.nodes.get(ref);
        if (!target) return;
        const world = this.landscape.worldPosition(target);
        const local = world.clone().sub(origin);
        const halo = new Mesh(
          new RingGeometry(target.radius * 2.1, target.radius * 2.35, 40),
          new MeshBasicMaterial({ color: tier.color, transparent: true, opacity: 0.85, depthWrite: false }),
        );
        halo.position.copy(local);
        halo.userData.billboard = true;
        this.extras.add(halo);
        this.surfacePoints.push(world);
      });
    });
    this.label(
      "stage-path-label",
      `${node.dependencies.length} dependency · ${node.directDependents.length} direct · ${
        tiers[2].refs.length
      } indirect dependent(s)`,
      new Vector3(0, -view.radius - 0.9, 0),
      { kind: "extra" },
    );
  }

  buildMigration(focus, view) {
    const stages = focus.stages || [];
    if (!stages.length) return;
    const points = stages.map((stage, index) =>
      index === 0 ? new Vector3(0, 0, 0) : new Vector3(3.4 * index + view.radius, -0.4 * index, 1.8 * index),
    );
    const path = new Line(
      new BufferGeometry().setFromPoints(points),
      new LineDashedMaterial({ color: "#5b9cf6", dashSize: 0.22, gapSize: 0.16, transparent: true, opacity: 0.9 }),
    );
    path.computeLineDistances();
    this.extras.add(path);
    stages.forEach((stage, index) => {
      const color = STAGE_HEX[stage.tone] || "#5b9cf6";
      if (index > 0) {
        const marker = new Mesh(new OctahedronGeometry(0.34), new MeshBasicMaterial({ color, transparent: true, opacity: 0.95 }));
        marker.position.copy(points[index]);
        this.extras.add(marker);
      }
      const label = this.label(
        `stage-path-label stage-path-${stage.tone}`,
        `${stage.label}: ${stage.value}`,
        points[index].clone().add(new Vector3(0, index === 0 ? -view.radius - 1.3 : 0.6, 0)),
        { kind: "extra" },
      );
      if (stage.note) {
        const note = document.createElement("span");
        note.className = "stage-path-note";
        note.textContent = stage.note;
        label.element.appendChild(note);
      }
      this.surfacePoints.push(this.group.position.clone().add(points[index]));
    });
  }

  buildEvidence(focus, view) {
    const steps = focus.evidenceSteps || [];
    steps.forEach((step, index) => {
      const position = new Vector3(-view.radius - 1.6, 0.9 - index * 0.62, 0.6);
      const tile = new Mesh(
        new PlaneGeometry(0.34, 0.34),
        new MeshBasicMaterial({ color: CHAIN_HEX[step.status] || CHAIN_HEX.unknown, transparent: true, opacity: 0.95, depthWrite: false }),
      );
      tile.position.copy(position);
      tile.userData.billboard = true;
      this.extras.add(tile);
      this.label(
        `stage-path-label stage-evidence-${step.status}`,
        `${index + 1}. ${step.label} — ${CHAIN_LABEL[step.status] || step.status}`,
        position.clone().add(new Vector3(-0.3, 0.2, 0)),
        { kind: "extra", align: "right" },
      );
      this.surfacePoints.push(this.group.position.clone().add(position));
    });
  }

  /** World-space points the camera should frame for the current surface. */
  framePoints() {
    if (!this.focus || !this.view) return [];
    return [this.landscape.worldPosition(this.view), ...this.surfacePoints];
  }

  pickTargets() {
    return [...this.anchors.values()].map((anchor) => anchor.plate);
  }

  setHovered(target) {
    const key = target?.surface || null;
    if (key === this.hoveredKey) return;
    this.hoveredKey = key;
    this.anchors.forEach((anchor, anchorKey) => {
      anchor.plate.scale.setScalar(anchorKey === key ? 1.12 : 1);
    });
    this.engine?.requestFrame();
  }

  onPick(target) {
    this.onSurface?.(target.surface === this.focus?.activeSurface ? null : target.surface);
  }

  update({ camera }) {
    // Plates and billboards face the camera; runs only on rendered frames
    // and never asks for more frames by itself.
    this.anchors.forEach((anchor) => anchor.plate.quaternion.copy(camera.quaternion));
    this.extras.children.forEach((child) => {
      if (child.userData.billboard) child.quaternion.copy(camera.quaternion);
    });
    return false;
  }

  labelState(label) {
    if (!this.focus) return { show: false };
    if (label.kind === "anchor") {
      const active = label.key === this.focus.activeSurface || label.key === this.hoveredKey;
      return { show: true, emphasis: active, priority: active ? 0 : 1 };
    }
    return { show: true, emphasis: true, priority: 0 };
  }

  dispose() {
    this.clear();
  }
}
