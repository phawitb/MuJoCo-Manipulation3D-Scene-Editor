import { describe, expect, it } from "vitest";
import { instantiateAsset } from "./importedAssets";
import type { Asset, SceneObject } from "./types";

const asset: Asset = {
  id: "imported_abc",
  name: "Sensor",
  category: "Imported",
  imported: true,
  dimensions: [0.06, 0.04, 0.02],
  mass: 0.045,
  color: "#123456",
  description: "MuJoCo package",
};
const template: SceneObject = {
  id: "imported_template",
  name: "Sensor",
  asset: "mujoco",
  position: [0, 0, 0],
  quaternion: [1, 0, 0, 0],
  scale: 2,
  mass: 0.045,
  color: "#123456",
  collision: true,
  friction: [0.6, 0.002, 0.0001],
  package_friction_override: false,
  package_color_override: false,
  package: {
    version: 1,
    source: "sensor.xml",
    dimensions: [0.03, 0.02, 0.01],
    mass: 0.045,
    com: [0.001, 0.002, 0],
    inertia: [1, 2, 3, 0, 0, 0],
    meshes: [],
    geoms: [
      { group: 2, contype: 0, conaffinity: 0 },
      { group: 3, contype: 1, conaffinity: 1 },
    ],
    sites: { grasp: [0.001, 0, 0] },
    provenance: { mass_source: "estimated" },
  },
};

describe("imported library insertion", () => {
  it("creates independent scene IDs and preserves all portable physics", () => {
    const first = instantiateAsset(asset, [0.1, 0, 0.8], template);
    const second = instantiateAsset(asset, [0.2, 0, 0.8], template);
    expect(first.id).not.toBe(second.id);
    expect(first.id).toMatch(/^[a-zA-Z][a-zA-Z0-9_-]{0,63}$/);
    expect(first.asset).toBe("mujoco");
    expect(first.package).toEqual(template.package);
    expect(first.scale).toBe(2);
    expect(first.friction).toEqual([0.6, 0.002, 0.0001]);
    expect(first.position).toEqual([0.1, 0, 0.8]);
    first.package!.sites.grasp[0] = 9;
    expect(second.package!.sites.grasp[0]).toBe(0.001);
    expect(template.package!.sites.grasp[0]).toBe(0.001);
  });
  it("never turns a missing imported template into a procedural object", () => {
    expect(() => instantiateAsset(asset, [0, 0, 0.8])).toThrow(/template/i);
  });
});
