import { Matrix4 } from "three";
import { toThreeQuaternion } from "./math";
import type { Asset, SceneObject, Table, Vec3 } from "./types";
export function objectDimensions(object: SceneObject, assets: Asset[]): Vec3 {
  const dimensions = assets.find((a) => a.id === object.asset)?.dimensions;
  if (dimensions) return dimensions.map((v) => v * object.scale) as Vec3;
  if (object.package)
    return object.package.dimensions.map((v) => v * object.scale) as Vec3;
  if (object.mesh)
    return [0, 1, 2].map((axis) => {
      let low = Infinity,
        high = -Infinity;
      for (let i = axis; i < object.mesh!.vertices.length; i += 3) {
        low = Math.min(low, object.mesh!.vertices[i]);
        high = Math.max(high, object.mesh!.vertices[i]);
      }
      return (high - low) * object.scale;
    }) as Vec3;
  return [0.04, 0.04, 0.04];
}
export function nudgePosition(
  object: SceneObject,
  dimensions: Vec3,
  table: Table,
  key: string,
  fine: boolean,
): Vec3 {
  const step = fine ? 0.001 : 0.01;
  const p = [...object.position] as Vec3;
  if (key === "ArrowRight") p[0] += step;
  if (key === "ArrowLeft") p[0] -= step;
  if (key === "ArrowUp") p[1] += step;
  if (key === "ArrowDown") p[1] -= step;
  const m = new Matrix4().makeRotationFromQuaternion(
    toThreeQuaternion(object.quaternion),
  ).elements;
  const half = [0, 1].map((axis) =>
    dimensions.reduce(
      (sum, d, i) => sum + (Math.abs(m[i * 4 + axis]) * d) / 2,
      0,
    ),
  );
  const limits = [table.width / 2 - half[0], table.depth / 2 - half[1]];
  if (limits.some((v) => v < 0))
    throw Error("Object is larger than the tabletop.");
  p[0] = Math.max(-limits[0], Math.min(limits[0], p[0]));
  p[1] = Math.max(-limits[1], Math.min(limits[1], p[1]));
  return p;
}
