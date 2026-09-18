// Enterprise cryptographic posture, anchored behind the landscape.
//
// Every value comes from GET /api/summary as already shown in the HTML
// posture panel: the readiness arc uses the dashboard's readiness
// percentage, the outer ring is the real risk-severity distribution, and
// the four pylons carry the four headline counts. Pylons are equal height
// on purpose -- their numbers are shown as labels, never encoded as a
// height that would imply a new metric.

import {
  BoxGeometry,
  Color,
  EdgesGeometry,
  Group,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  RingGeometry,
  TorusGeometry,
  Vector3,
} from "three";

import { disposeObject } from "./SpatialEngine";

const SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SEVERITY_HEX = { CRITICAL: "#ef4444", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#22c55e" };
const TONE_HEX = { low: "#22c55e", medium: "#eab308", high: "#f97316", critical: "#ef4444" };

const RING_CENTER = new Vector3(0, 5.2, 0);
const PYLONS = [
  { key: "assets", x: -15 },
  { key: "priority", x: -9 },
  { key: "pqc", x: 9 },
  { key: "actions", x: 15 },
];

export class PostureLayer {
  constructor({ origin = new Vector3(0, 0, -20), onMetric } = {}) {
    this.group = new Group();
    this.group.position.copy(origin);
    this.onMetric = onMetric;
    this.pickPriority = 2;
    this.presence = 1;
    this.targetPresence = 1;
    this.hoveredKey = null;
    this.activeMetric = null;
    this.labels = [];
    this.materials = [];
    this.pylons = new Map();
    this.content = new Group();
    this.group.add(this.content);
  }

  attach(engine) {
    this.engine = engine;
  }

  track(material, baseOpacity) {
    material.transparent = true;
    material.userData.baseOpacity = baseOpacity;
    material.opacity = baseOpacity;
    this.materials.push(material);
    return material;
  }

  /** posture = { readinessPercent, tone, distribution, metrics: [{ key, title, value }] } */
  setPosture(posture) {
    this.clear();
    if (!posture) return;
    const { readinessPercent, tone, distribution = {}, metrics = [] } = posture;

    // Base plate the posture instruments stand on.
    const plate = new Mesh(
      new RingGeometry(0.2, 18.5, 64, 1),
      this.track(new MeshBasicMaterial({ color: "#0c1a33", depthWrite: false }), 0.35),
    );
    plate.rotation.x = -Math.PI / 2;
    plate.position.y = 0.02;
    this.content.add(plate);

    // Readiness: full track + value arc, standing upright, facing the landscape.
    const track = new Mesh(new TorusGeometry(3.2, 0.16, 12, 96), this.track(new MeshBasicMaterial({ color: "#1c2740" }), 0.9));
    track.position.copy(RING_CENTER);
    this.content.add(track);

    const fraction = Math.min(Math.max((readinessPercent || 0) / 100, 0), 1);
    if (fraction > 0) {
      const color = new Color(TONE_HEX[tone] || "#22d3ee");
      const arc = new Mesh(
        new TorusGeometry(3.2, 0.22, 12, 96, Math.PI * 2 * fraction),
        this.track(new MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.55, roughness: 0.4 }), 1),
      );
      arc.position.copy(RING_CENTER);
      // Start at 12 o'clock and run clockwise, like the HTML readiness ring.
      arc.rotation.z = -Math.PI / 2;
      arc.scale.x = -1;
      this.content.add(arc);
    }

    // Severity distribution: outer segmented ring, slightly behind.
    const total = SEVERITY_ORDER.reduce((sum, key) => sum + (distribution[key] || 0), 0);
    let cursor = 0;
    SEVERITY_ORDER.forEach((key) => {
      const count = distribution[key] || 0;
      if (!total || !count) return;
      const share = count / total;
      const gap = 0.03;
      const segment = new Mesh(
        new TorusGeometry(4.3, 0.09, 8, 96, Math.max(Math.PI * 2 * share - gap, 0.01)),
        this.track(new MeshBasicMaterial({ color: SEVERITY_HEX[key] }), 0.85),
      );
      segment.position.copy(RING_CENTER).add(new Vector3(0, 0, -0.35));
      segment.rotation.z = -Math.PI / 2 - Math.PI * 2 * cursor - gap / 2;
      segment.scale.x = -1;
      this.content.add(segment);
      cursor += share;
    });

    this.addLabel("stage-posture-label stage-posture-readiness", `${readinessPercent}% quantum readiness`, RING_CENTER.clone().add(new Vector3(0, 5.1, 0)), "readiness");
    this.addLabel(
      "stage-posture-label stage-posture-severity",
      SEVERITY_ORDER.map((key) => `${distribution[key] || 0} ${key.toLowerCase()}`).join(" · "),
      RING_CENTER.clone().add(new Vector3(0, -4.9, 0)),
      "severity",
    );

    // Headline metric pylons.
    PYLONS.forEach(({ key, x }) => {
      const metric = metrics.find((item) => item.key === key);
      if (!metric) return;
      const pylon = new Group();
      pylon.position.set(x, 0, 0);
      const body = new Mesh(
        new BoxGeometry(1.4, 4.2, 1.4),
        this.track(new MeshStandardMaterial({ color: "#0f1a33", emissive: "#12305a", emissiveIntensity: 0.35, roughness: 0.6 }), 0.92),
      );
      body.position.y = 2.1;
      pylon.add(body);
      const frame = new LineSegments(
        new EdgesGeometry(body.geometry),
        this.track(new LineBasicMaterial({ color: metric.interactive ? "#22d3ee" : "#2e4a7a" }), 0.7),
      );
      frame.position.copy(body.position);
      pylon.add(frame);
      const cap = new Mesh(
        new BoxGeometry(1.5, 0.12, 1.5),
        this.track(new MeshBasicMaterial({ color: metric.tone === "critical" ? "#f97316" : metric.tone === "cyan" ? "#22d3ee" : "#5b9cf6" }), 0.9),
      );
      cap.position.y = 4.26;
      pylon.add(cap);
      const hit = new Mesh(new BoxGeometry(2.2, 5, 2.2), new MeshBasicMaterial({ visible: false }));
      hit.position.y = 2.4;
      hit.userData = { id: key, metric: key, interactive: Boolean(metric.interactive) };
      pylon.add(hit);
      this.content.add(pylon);
      this.pylons.set(key, { pylon, frame, cap, hit, metric });
      this.addLabel("stage-posture-label stage-posture-metric", `${metric.value} · ${metric.title}`, new Vector3(x, 5.2, 0), key);
    });

    this.applyActive();
    this.engine?.requestFrame();
  }

  addLabel(className, text, position, key) {
    const label = this.engine.addLabel({ layer: this, className, text, position, owner: this.group, collision: "box" });
    label.key = key;
    label.element.dataset.postureKey = key;
    this.labels.push(label);
  }

  clear() {
    [...this.content.children].forEach((child) => {
      this.content.remove(child);
      disposeObject(child);
    });
    this.engine?.removeLabels(this);
    this.labels = [];
    this.materials = [];
    this.pylons.clear();
  }

  /** 1 = posture in focus (global view), lower when the user works elsewhere. */
  setPresence(value) {
    this.targetPresence = value;
    this.engine?.requestFrame();
  }

  setActiveMetric(metric) {
    this.activeMetric = metric;
    this.applyActive();
  }

  applyActive() {
    this.pylons.forEach(({ frame, metric }, key) => {
      const active = key === this.activeMetric;
      const hovered = key === this.hoveredKey;
      frame.material.color.set(active ? "#67e8f9" : hovered && metric.interactive ? "#a5f3fc" : metric.interactive ? "#22d3ee" : "#2e4a7a");
    });
    this.engine?.requestFrame();
  }

  anchorPositions() {
    const origin = this.group.position;
    return [
      origin.clone().add(new Vector3(-16, 0, 0)),
      origin.clone().add(new Vector3(16, 0, 0)),
      origin.clone().add(new Vector3(0, 10.5, 0)),
      origin.clone().add(new Vector3(0, 0, 3)),
    ];
  }

  pickTargets() {
    if (this.presence < 0.3) return [];
    return [...this.pylons.values()].filter((item) => item.metric.interactive).map((item) => item.hit);
  }

  setHovered(target) {
    this.hoveredKey = target?.metric || null;
    this.applyActive();
  }

  onPick(target) {
    if (target.interactive) this.onMetric?.(target.metric);
  }

  update({ blend }) {
    const delta = this.targetPresence - this.presence;
    if (Math.abs(delta) < 0.003) {
      if (this.presence !== this.targetPresence) {
        this.presence = this.targetPresence;
        this.applyPresence();
      }
      return false;
    }
    this.presence += delta * blend;
    this.applyPresence();
    return true;
  }

  applyPresence() {
    this.materials.forEach((material) => {
      material.opacity = material.userData.baseOpacity * (0.18 + 0.82 * this.presence);
    });
    this.group.visible = this.presence > 0.02;
  }

  labelState(label) {
    const show = this.group.visible && this.presence > 0.55;
    // In the posture view its instruments' labels are placed first.
    return { show, emphasis: label.key === this.activeMetric, priority: this.presence > 0.9 ? 0 : 1 };
  }

  dispose() {
    this.clear();
  }
}
