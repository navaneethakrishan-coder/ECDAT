// Simulation space: the What-If result currently on screen, staged next
// to the real finding.
//
// The real node stays exactly where the landscape put it (frozen: a still
// dashed frame, no pulse). A translucent "ghost" sits beside it at the
// height the landscape's own risk scale gives the backend's simulated
// risk score, joined by a dashed link. Labels carry the backend's before /
// after values and say "real" and "hypothetical" explicitly. Nothing is
// computed here and the real finding is never modified.

import {
  BufferGeometry,
  Group,
  Line,
  LineBasicMaterial,
  LineDashedMaterial,
  Mesh,
  MeshBasicMaterial,
  RingGeometry,
  SphereGeometry,
  Vector3,
} from "three";

import { disposeObject } from "./SpatialEngine";

function format(value) {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

export class SimulationLayer {
  constructor({ landscape } = {}) {
    this.group = new Group();
    this.landscape = landscape;
    this.points = [];
    this.active = null;
  }

  attach(engine) {
    this.engine = engine;
  }

  /** simulation = backend summary published by the What-If simulator, or null. */
  setSimulation(simulation, heightScale) {
    const view = simulation ? this.landscape.nodes.get(simulation.bomRef) : null;
    const signature = simulation && view ? JSON.stringify(simulation) : null;
    if (signature === this.signature) return;
    this.signature = signature;
    this.clear();
    this.active = signature ? simulation : null;
    if (!this.active) {
      this.engine?.requestFrame();
      return;
    }

    const origin = this.landscape.worldPosition(view);
    this.group.position.copy(origin);
    const realY = view.node.position.y;
    const afterScore = simulation.risk?.after?.score;
    const ghostY = typeof afterScore === "number" ? (afterScore / 100) * heightScale - realY : 0;
    const ghostOffset = new Vector3(3.6, ghostY, 1.6);

    // Frozen frame around the real node.
    const frame = new Mesh(
      new RingGeometry(view.radius * 1.9, view.radius * 2.02, 48),
      new MeshBasicMaterial({ color: "#e2e8f0", transparent: true, opacity: 0.7, depthWrite: false }),
    );
    frame.userData.billboard = true;
    this.group.add(frame);

    // Hypothetical ghost.
    const ghost = new Mesh(
      new SphereGeometry(view.radius, 24, 16),
      new MeshBasicMaterial({ color: "#a78bfa", wireframe: true, transparent: true, opacity: 0.75 }),
    );
    ghost.position.copy(ghostOffset);
    this.group.add(ghost);
    const ghostHalo = new Mesh(
      new RingGeometry(view.radius * 1.5, view.radius * 1.62, 48),
      new MeshBasicMaterial({ color: "#a78bfa", transparent: true, opacity: 0.8, depthWrite: false }),
    );
    ghostHalo.position.copy(ghostOffset);
    ghostHalo.userData.billboard = true;
    this.group.add(ghostHalo);

    const link = new Line(
      new BufferGeometry().setFromPoints([new Vector3(0, 0, 0), ghostOffset]),
      new LineDashedMaterial({ color: "#a78bfa", dashSize: 0.2, gapSize: 0.15, transparent: true, opacity: 0.9 }),
    );
    link.computeLineDistances();
    this.group.add(link);

    const drop = new Line(
      new BufferGeometry().setFromPoints([ghostOffset, new Vector3(ghostOffset.x, -realY, ghostOffset.z)]),
      new LineBasicMaterial({ color: "#a78bfa", transparent: true, opacity: 0.3 }),
    );
    this.group.add(drop);

    const readiness = simulation.readiness;
    this.addLabel(
      "stage-sim-label stage-sim-real",
      `Current · real — risk ${format(simulation.risk?.before?.score)} ${simulation.risk?.before?.severity || ""}`,
      new Vector3(0, -view.radius - 1.4, 0),
      readiness ? `Readiness ${readiness.before}%` : null,
    );
    this.addLabel(
      "stage-sim-label stage-sim-hypothetical",
      `Simulated · hypothetical — ${simulation.pqcComponent}: risk ${format(afterScore)} ${simulation.risk?.after?.severity || ""}`,
      ghostOffset.clone().add(new Vector3(0, view.radius + 0.6, 0)),
      readiness ? `Readiness ${readiness.after}%` : null,
    );

    this.points = [origin.clone(), origin.clone().add(ghostOffset), origin.clone().add(new Vector3(ghostOffset.x, -realY, ghostOffset.z))];
    this.engine?.requestFrame();
  }

  addLabel(className, text, position, detail) {
    const label = this.engine.addLabel({ layer: this, className, text, position, owner: this.group, collision: "box" });
    if (detail) {
      const span = document.createElement("span");
      span.className = "stage-sim-detail";
      span.textContent = detail;
      label.element.appendChild(span);
    }
  }

  clear() {
    [...this.group.children].forEach((child) => {
      this.group.remove(child);
      disposeObject(child);
    });
    this.engine?.removeLabels(this);
    this.points = [];
  }

  framePoints() {
    return this.points;
  }

  update({ camera }) {
    this.group.children.forEach((child) => {
      if (child.userData.billboard) child.quaternion.copy(camera.quaternion);
    });
    return false;
  }

  labelState() {
    return { show: Boolean(this.active), emphasis: true, priority: 0 };
  }

  dispose() {
    this.clear();
  }
}
