export const jointNames = [
  "shoulder_pan",
  "shoulder_lift",
  "elbow_flex",
  "wrist_flex",
  "wrist_roll",
  "gripper",
];
export type CalibrationJoint = {
  name: string;
  zero_raw: number;
  direction: number;
  raw_min: number;
  raw_max: number;
  radians_per_tick: number;
};
export type Telemetry = {
  id: number;
  name: string;
  model: number;
  raw: number;
  position_rad: number | null;
  voltage: number;
  temperature: number;
  torque: boolean;
};
export type ConnectionStatus = {
  gym_execution?: { phase: string; message: string; session_id: string | null };
  connected: boolean;
  port: string | null;
  identity: string | null;
  owner_session_id: string | null;
  enabled: boolean;
  sync_mode: string;
  fault: string | null;
  calibrated: boolean;
  calibration: unknown;
  telemetry: Telemetry[];
  telemetry_age_s: number | null;
  target_rad: number[] | null;
  desired_rad: number[] | null;
  tracking_error_rad: number[] | null;
  compensation_rad: number[] | null;
  temperature_rechecks: number;
  lease_remaining_s: number;
};
export type Assignments = {
  back: number | null;
  front: number | null;
  wrist: number | null;
};
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const r = await fetch(`/api/connection${path}`, {
    method,
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const data = await r.json();
      msg =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail);
    } catch {}
    throw new Error(msg);
  }
  return r.json();
}
export type CameraResult = {
  index: number;
  available: boolean;
  image: string | null;
  error?: string;
  role?: string;
};
export type ConnectionSettings = {
  robot_port: string | null;
  assignments: Assignments;
};
export type Verification = {
  ok: boolean;
  robot: {
    ok: boolean;
    port: string | null;
    motor_count: number;
    calibrated: boolean;
    message: string;
  };
  cameras: CameraResult[];
  unassigned: string[];
};
