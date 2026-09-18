// Static architectural environment: floor grid, and (on the stage) a few
// structural planes and sparse points. Built once, never animated, never
// pickable -- it adds depth without asking the renderer for frames.

import {
  BufferGeometry,
  EdgesGeometry,
  Float32BufferAttribute,
  GridHelper,
  Group,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  PlaneGeometry,
  Points,
  PointsMaterial,
} from "three";

import { disposeObject } from "./SpatialEngine";

function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class EnvironmentLayer {
  constructor({ size = 30, structures = false, particles = false } = {}) {
    this.group = new Group();
    this.options = { structures, particles };
    this.build(size);
  }

  setSize(size) {
    if (size === this.size) return;
    [...this.group.children].forEach((child) => {
      this.group.remove(child);
      disposeObject(child);
    });
    this.build(size);
    this.engine?.requestFrame();
  }

  attach(engine) {
    this.engine = engine;
  }

  build(size) {
    this.size = size;
    const grid = new GridHelper(size, Math.round(size / 1.5), "#1f3a66", "#132340");
    grid.material.transparent = true;
    grid.material.opacity = 0.35;
    grid.material.depthWrite = false;
    this.group.add(grid);

    if (this.options.structures) {
      // Two framed structural planes standing at the edges of the space.
      [
        { x: -size * 0.42, z: -size * 0.18, rotation: 0.55 },
        { x: size * 0.42, z: -size * 0.22, rotation: -0.6 },
      ].forEach(({ x, z, rotation }) => {
        const plane = new Mesh(
          new PlaneGeometry(size * 0.28, size * 0.2),
          new MeshBasicMaterial({ color: "#0d1d38", transparent: true, opacity: 0.18, depthWrite: false }),
        );
        plane.position.set(x, size * 0.1, z);
        plane.rotation.y = rotation;
        this.group.add(plane);
        const frame = new LineSegments(
          new EdgesGeometry(plane.geometry),
          new LineBasicMaterial({ color: "#2e4a7a", transparent: true, opacity: 0.35 }),
        );
        frame.position.copy(plane.position);
        frame.rotation.copy(plane.rotation);
        this.group.add(frame);
      });
    }

    if (this.options.particles) {
      const random = seeded(20260917);
      const positions = [];
      for (let i = 0; i < 160; i += 1) {
        positions.push((random() - 0.5) * size * 1.4, 1 + random() * size * 0.35, (random() - 0.5) * size * 1.2);
      }
      const geometry = new BufferGeometry();
      geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
      this.group.add(
        new Points(
          geometry,
          new PointsMaterial({ color: "#8fb3e6", size: 0.08, transparent: true, opacity: 0.35, depthWrite: false }),
        ),
      );
    }
  }
}
