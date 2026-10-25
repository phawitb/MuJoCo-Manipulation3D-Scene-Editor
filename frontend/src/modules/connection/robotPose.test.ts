import { describe, expect, it } from "vitest";
import { jointNames } from "./api";
import { measuredRobotPose } from "./robotPose";

describe("URDF encoder pose", () => {
  const rows = jointNames.map((name, i) => ({ name, position_rad: i / 10 }));
  it("maps by joint name regardless of motor response order; gripper remains radians", () => {
    expect(measuredRobotPose([...rows].reverse())).toEqual(
      Object.fromEntries(rows.map((r) => [r.name, r.position_rad])),
    );
  });
  it("does not invent zero angles for missing or invalid feedback", () => {
    expect(measuredRobotPose(rows.slice(1))).toBeNull();
    expect(
      measuredRobotPose(
        rows.map((r, i) => (i === 2 ? { ...r, position_rad: null } : r)),
      ),
    ).toBeNull();
    expect(
      measuredRobotPose(
        rows.map((r, i) => (i === 2 ? { ...r, position_rad: NaN } : r)),
      ),
    ).toBeNull();
  });
});
