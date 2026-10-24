import { describe, it, expect } from "vitest";
import {
  dropPosition,
  toThreeQuaternion,
  toMujocoQuaternion,
  validateDocument,
  defaultCameras,
} from "./math";

describe("coordinate contract", () => {
  it("converts quaternion order without changing rotation", () => {
    const wxyz = [0.70710678, 0, 0, 0.70710678] as [
      number,
      number,
      number,
      number,
    ];
    const q = toThreeQuaternion(wxyz);
    expect(q.w).toBe(wxyz[0]);
    expect(q.z).toBe(wxyz[3]);
    expect(toMujocoQuaternion(q)).toEqual(wxyz);
  });
  it("clamps all of an object footprint to the tabletop and places bottom above surface", () => {
    const p = dropPosition([5, -4, 0.75], [0.072, 0.072, 0.1], {
      width: 0.8,
      depth: 0.6,
      height: 0.75,
    });
    [0.364, -0.264, 0.802].forEach((x, i) => expect(p[i]).toBeCloseTo(x, 12));
  });
  it("rejects a surface smaller than the object", () => {
    expect(() =>
      dropPosition([0, 0, 0], [3, 3, 3], {
        width: 0.8,
        depth: 0.6,
        height: 0.75,
      }),
    ).toThrow();
  });
  it("rejects unsupported and malformed save files", () => {
    expect(() => validateDocument({ version: 4 })).toThrow();
    expect(() =>
      validateDocument({ version: 1, scene: {}, cameras: {} }),
    ).toThrow();
  });
  it("rejects imported top cameras tilted away from the tabletop", () => {
    const cameras = defaultCameras();
    cameras.top.position[0] = 0.5;
    expect(() =>
      validateDocument({
        version: 1,
        scene: { version: 1, objects: [], table: {}, robot: {} },
        cameras,
      }),
    ).toThrow("Top camera");
  });
  it("keeps camera records independent", () => {
    const cameras = defaultCameras();
    cameras.main.position[0] = 8;
    expect(cameras.top.position[0]).toBe(0);
    expect(defaultCameras().main.position[0]).not.toBe(8);
  });
});
