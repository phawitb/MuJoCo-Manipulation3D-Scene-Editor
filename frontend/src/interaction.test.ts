import { expect, it } from "vitest";
import { nudgePosition, objectDimensions } from "./interaction";
import type { SceneObject } from "./types";
const obj = {
  asset: "cube",
  position: [0, 0, 0.8],
  quaternion: [1, 0, 0, 0],
  scale: 1,
} as SceneObject;
it("moves arrows on world XY with fine shift steps, preserving height", () => {
  expect(
    nudgePosition(
      obj,
      [0.04, 0.04, 0.04],
      { width: 0.8, depth: 0.6, height: 0.75 },
      "ArrowUp",
      true,
    ),
  ).toEqual([0, 0.001, 0.8]);
  expect(
    nudgePosition(
      obj,
      [0.04, 0.04, 0.04],
      { width: 0.8, depth: 0.6, height: 0.75 },
      "ArrowLeft",
      false,
    ),
  ).toEqual([-0.01, 0, 0.8]);
});
it("clamps the rotated object footprint to the tabletop", () => {
  const rotated = {
    ...obj,
    position: [0.38, 0, 0.8],
    quaternion: [Math.SQRT1_2, 0, 0, Math.SQRT1_2],
  } as SceneObject;
  expect(
    nudgePosition(
      rotated,
      [0.2, 0.06, 0.01],
      { width: 0.8, depth: 0.6, height: 0.75 },
      "ArrowRight",
      false,
    )[0],
  ).toBeCloseTo(0.37);
});
it("uses actual imported mesh bounds and object scale", () => {
  const mesh = {
    ...obj,
    asset: "mesh",
    scale: 2,
    mesh: {
      vertices: [-0.1, -0.02, -0.03, 0.1, 0.02, 0.03],
      faces: [],
      filename: "a.obj",
    },
  } as SceneObject;
  expect(objectDimensions(mesh, [])).toEqual([0.4, 0.08, 0.12]);
});
