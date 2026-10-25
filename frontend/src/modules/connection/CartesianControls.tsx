import { useEffect, useState } from "react";
import { api, type ConnectionStatus } from "./api";

export default function CartesianControls({
  sid,
  status,
  owned,
  onError,
  refresh,
}: {
  sid: string;
  status: ConnectionStatus;
  owned: boolean;
  onError: (message: string) => void;
  refresh: () => Promise<unknown>;
}) {
  const [xyz, setXyz] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const tool = status.tool;
  useEffect(() => {
    setXyz(null);
  }, [sid, status.control_epoch]);
  if (!tool) return null;
  const values =
    xyz ?? tool.measured.position.map((v) => (v * 1000).toFixed(1));
  const blocked =
    busy ||
    !owned ||
    !status.calibrated ||
    status.limit_recovery_active ||
    !!status.limit_violations?.length ||
    status.sync_mode !== "off" ||
    ["preparing", "running"].includes(status.gym_execution?.phase ?? "") ||
    status.telemetry.length !== 6 ||
    !status.telemetry.every((r) => r.torque) ||
    status.telemetry_age_s === null ||
    status.telemetry_age_s > 0.3;
  const move = async () => {
    const position = values.map((v) => Number(v) / 1000);
    if (
      values.some((v) => !v.trim()) ||
      position.some((v) => !Number.isFinite(v))
    ) {
      onError("Enter a number for X, Y and Z.");
      return;
    }
    setBusy(true);
    onError("");
    try {
      await api("/tool-target", "POST", {
        session_id: sid,
        control_epoch: status.control_epoch,
        position,
      });
      await refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="connection-card" aria-label="Tool position control">
      <h2>
        Tool position{" "}
        <span className="connection-badge">
          {status.limit_violations?.length
            ? "Check joint limits"
            : tool.phase === "holding"
              ? "At target"
              : tool.phase === "moving"
                ? "Moving"
                : "Ready"}
        </span>
      </h2>
      <p className="connection-hint">
        Gripper position in the scene · millimetres. Motion keeps the current
        tool orientation and jaw opening; the whole arm is checked for
        collisions.
      </p>
      <div className="tool-coordinate-grid">
        {values.map((value, i) => (
          <label key={i}>
            {["X", "Y", "Z"][i]} target (mm)
            <input
              aria-label={`${["X", "Y", "Z"][i]} tool target in millimetres`}
              type="number"
              step="1"
              value={value}
              onChange={(e) =>
                setXyz(values.map((v, j) => (j === i ? e.target.value : v)))
              }
            />
            <small>
              Encoder estimate: {(tool.measured.position[i] * 1000).toFixed(1)}{" "}
              mm
            </small>
          </label>
        ))}
      </div>
      <div className="connection-actions">
        <button
          disabled={busy}
          onClick={() =>
            setXyz(tool.measured.position.map((v) => (v * 1000).toFixed(1)))
          }
        >
          Use current position
        </button>
        <button
          className="primary"
          disabled={blocked}
          onClick={() => void move()}
        >
          {busy ? "Checking path…" : "Move gripper"}
        </button>
      </div>
      {tool.error && (
        <p role="status">
          Distance to target: {tool.error.position_mm.toFixed(2)} mm ·
          Orientation: {tool.error.orientation_deg.toFixed(2)}° · Jaw:{" "}
          {tool.error.opening_deg.toFixed(2)}°
        </p>
      )}
      <p className="connection-hint">
        Position is estimated from encoders and the robot model. Camera
        calibration and physical grasp verification are not available. Arrival
        tolerance: 3 mm, 3° orientation, 1.5° jaw.
      </p>
    </section>
  );
}
