import { Euler, Quaternion, MathUtils } from "three";
import type { Cameras, Quat, SavedDocument, Table, Vec3 } from "./types";
export const toThreeQuaternion = (q: Quat) =>
  new Quaternion(q[1], q[2], q[3], q[0]);
export const toMujocoQuaternion = (q: Quaternion): Quat => [q.w, q.x, q.y, q.z];
export const rotationDegrees = (q: Quat): Vec3 => {
  const e = new Euler().setFromQuaternion(toThreeQuaternion(q), "XYZ");
  return [e.x, e.y, e.z].map(MathUtils.radToDeg) as Vec3;
};
export const fromDegrees = (v: Vec3): Quat =>
  toMujocoQuaternion(
    new Quaternion().setFromEuler(
      new Euler(...(v.map(MathUtils.degToRad) as Vec3), "XYZ"),
    ),
  );
export function dropPosition(hit: Vec3, dimensions: Vec3, table: Table): Vec3 {
  if (dimensions[0] > table.width || dimensions[1] > table.depth)
    throw new Error("Object is larger than the tabletop");
  return [
    MathUtils.clamp(
      hit[0],
      -(table.width - dimensions[0]) / 2,
      (table.width - dimensions[0]) / 2,
    ),
    MathUtils.clamp(
      hit[1],
      -(table.depth - dimensions[1]) / 2,
      (table.depth - dimensions[1]) / 2,
    ),
    table.height + dimensions[2] / 2 + 0.002,
  ];
}
export const defaultCameras = (): Cameras => ({
  main: { position: [1.05, -1.25, 1.55], target: [0, 0, 0.77], zoom: 1 },
  top: { position: [0, 0, 2.6], target: [0, 0, 0.75], zoom: 320 },
});
const finiteVector = (v: unknown, n: number) =>
  Array.isArray(v) &&
  v.length === n &&
  v.every(
    (x) => typeof x === "number" && Number.isFinite(x) && Math.abs(x) <= 100,
  );
export function validateDocument(input: unknown): SavedDocument {
  const d = input as SavedDocument;
  if (
    !d ||
    d.version !== 1 ||
    !d.scene ||
    d.scene.version !== 1 ||
    !Array.isArray(d.scene.objects) ||
    !d.scene.table ||
    !d.scene.robot ||
    d.scene.objects.length > 64
  )
    throw new Error("Not a supported Scene Studio file (version 1)");
  if (d.cameras)
    for (const kind of ["main", "top"] as const) {
      const c = d.cameras[kind];
      if (
        !c ||
        !finiteVector(c.position, 3) ||
        !finiteVector(c.target, 3) ||
        !Number.isFinite(c.zoom) ||
        c.zoom <= 0 ||
        c.zoom > 10000
      )
        throw new Error("Invalid camera settings");
      if (Math.hypot(...c.position.map((v, i) => v - c.target[i])) < 0.01)
        throw new Error("Camera must be away from its target");
      if (
        kind === "top" &&
        (Math.abs(c.position[0] - c.target[0]) > 1e-5 ||
          Math.abs(c.position[1] - c.target[1]) > 1e-5 ||
          c.position[2] <= c.target[2])
      )
        throw new Error("Top camera must look vertically down at the table");
    }
  return d; // Full scene validation happens authoritatively on the server.
}
export function readCameras(): Cameras {
  try {
    const cameras = JSON.parse(localStorage.getItem("so101.cameras") || "null");
    const d = {
      version: 1,
      scene: { version: 1, objects: [], table: {}, robot: {} },
      cameras,
    };
    if (cameras) return validateDocument(d).cameras!;
  } catch {
    /* Invalid local state falls back to defaults. */
  }
  return defaultCameras();
}
