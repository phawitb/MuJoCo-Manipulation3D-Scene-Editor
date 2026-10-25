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
export type EpisodeReport = {
  id: string;
  session_id: string;
  outcome: "completed" | "stopped";
  reason: string;
  samples: number;
  duration_s: number;
  last_sample_age_s: number | null;
  measurement_source: "encoder_fk";
  environment_source: "simulation_rehearsal";
  object_verified: false;
  last_error: ToolError | null;
  peak_target_distance_mm: number;
  rms_target_distance_mm: number | null;
};
export type RobotMount = {
  table_z: number;
  quaternion: [number, number, number, number];
  pedestal: {
    position: [number, number, number];
    size: [number, number, number];
  } | null;
};
export type ToolPose = {
  position: [number, number, number];
  quaternion: [number, number, number, number];
  opening_rad: number;
};
export type ToolError = {
  position_mm: number;
  orientation_deg: number;
  opening_deg: number;
};
export type ToolStatus = {
  phase: string;
  frame: "world";
  tool_frame: "gripperframe";
  measurement_source: "encoder_fk";
  object_verified: false;
  measured: ToolPose;
  target: ToolPose | null;
  error: ToolError | null;
};
export type ConnectionStatus = {
  tool?: ToolStatus | null;
  robot_mount?: RobotMount | null;
  control_epoch: number;
  manual_phase?: "moving" | "holding" | null;
  limit_recovery_active?: boolean;
  manual_target?: number[] | null;
  control_limits?: [number, number][] | null;
  limit_violations?: {
    name: string;
    angle_rad: number;
    min_rad: number;
    max_rad: number;
    raw: number;
    raw_min: number;
    raw_max: number;
  }[];
  robot_preview?: {
    points: [number, number, number][];
    fingers: [number, number, number][];
  } | null;
  gym_execution?: {
    phase: string;
    message: string;
    session_id: string | null;
    report?: EpisodeReport | null;
  };
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
