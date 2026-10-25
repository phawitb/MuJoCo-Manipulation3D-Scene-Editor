import { jointNames, type Telemetry } from "./api";

// Feedback is already calibrated to Gym radians, including the gripper.
export function measuredRobotPose(
  rows: Pick<Telemetry, "name" | "position_rad">[],
): Record<string, number> | null {
  const pose: Record<string, number> = {};
  for (const name of jointNames) {
    const angle = rows.find((row) => row.name === name)?.position_rad;
    if (angle == null || !Number.isFinite(angle)) return null;
    pose[name] = angle;
  }
  return pose;
}
