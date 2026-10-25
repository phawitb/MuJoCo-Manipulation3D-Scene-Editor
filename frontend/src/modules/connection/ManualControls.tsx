import { useEffect, useRef, useState } from "react";
import RobotModel from "./RobotModel";
import { api, jointNames, type ConnectionStatus } from "./api";
import { LatestTarget } from "./latestTarget";

const degrees = (v: number) => (v * 180) / Math.PI;
const labels = [
  "Base rotation",
  "Shoulder",
  "Elbow",
  "Wrist pitch",
  "Wrist rotation",
  "Gripper",
];
export default function ManualControls({
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
  const [target, setTarget] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);
  const draft = useRef<number[] | null>(null);
  const queue = useRef<LatestTarget | null>(null);
  const handlers = useRef({ onError, refresh });
  handlers.current = { onError, refresh };
  useEffect(() => {
    const sender = new LatestTarget(
      (q) =>
        api("/target", "POST", {
          session_id: sid,
          joints: q,
          control_epoch: status.control_epoch,
        }),
      (e) => {
        draft.current = null;
        setTarget(null);
        handlers.current.onError(String(e));
        void handlers.current.refresh();
      },
    );
    queue.current = sender;
    return () => {
      sender.dispose();
      queue.current = null;
    };
  }, [sid, status.control_epoch]);
  useEffect(() => {
    if (!status.enabled || status.fault) {
      draft.current = null;
      setTarget(null);
    }
  }, [status.enabled, status.fault]);
  const measured = status.telemetry.map((row) => row.position_rad ?? 0);
  const torqueOn =
    status.telemetry.length === 6 &&
    status.telemetry.every((row) => row.torque);
  const allowed =
    owned &&
    status.calibrated &&
    status.sync_mode === "off" &&
    status.gym_execution?.phase !== "preparing" &&
    status.gym_execution?.phase !== "running";
  const act = async (path: string, extra = {}) => {
    setBusy(true);
    onError("");
    if (path === "/stop" || path === "/torque") void queue.current?.cancel();
    else await queue.current?.cancel();
    draft.current = null;
    setTarget(null);
    try {
      await api(path, "POST", {
        session_id: sid,
        ...(path === "/stop" ? {} : { control_epoch: status.control_epoch }),
        ...extra,
      });
      await refresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const change = (index: number, value: number) => {
    const q = [
      ...(draft.current ??
        status.manual_target ??
        status.desired_rad ??
        measured),
    ];
    q[index] = (value * Math.PI) / 180;
    draft.current = q;
    setTarget(q);
    queue.current?.push(q);
  };
  return (
    <section className="connection-card manual-card">
      <h2>
        Direct robot control{" "}
        <span className={`connection-badge ${torqueOn ? "ok" : ""}`}>
          {status.manual_phase === "holding"
            ? "Holding target"
            : status.manual_phase === "moving"
              ? "Moving"
              : torqueOn
                ? "Torque on"
                : "Torque off"}
        </span>
      </h2>
      <div className="manual-layout">
        <RobotModel telemetry={status.telemetry} />
        <div className="manual-sliders">
          {jointNames.map((name, i) => {
            const limits = status.control_limits?.[i];
            const value =
              (target ??
                status.manual_target ??
                status.desired_rad ??
                measured)[i] ?? 0;
            return (
              <label key={name} className="manual-joint">
                <span>
                  {labels[i]}{" "}
                  <output>
                    {degrees(measured[i] ?? 0).toFixed(1)}°{" "}
                    <small>measured</small>
                  </output>
                </span>
                <input
                  aria-label={`${labels[i]} target`}
                  type="range"
                  min={Math.ceil(degrees(limits?.[0] ?? -Math.PI) * 10) / 10}
                  max={Math.floor(degrees(limits?.[1] ?? Math.PI) * 10) / 10}
                  step="0.1"
                  value={degrees(value)}
                  disabled={!allowed || !torqueOn || busy || !limits}
                  onChange={(e) => change(i, Number(e.target.value))}
                />
                <small>
                  {degrees(limits?.[0] ?? 0).toFixed(0)}°{" "}
                  <span>Target {degrees(value).toFixed(1)}°</span>{" "}
                  {degrees(limits?.[1] ?? 0).toFixed(0)}°
                </small>
              </label>
            );
          })}
        </div>
      </div>
      <div className="connection-actions manual-actions">
        <button
          disabled={!allowed || !torqueOn || busy}
          onClick={() => void act("/home")}
        >
          Home position
        </button>
        <button
          disabled={!allowed || !torqueOn || busy}
          onClick={() => void act("/match-gym")}
        >
          Move robot to Gym pose
        </button>
        <button
          disabled={!allowed || torqueOn || busy || status.enabled}
          onClick={() => void act("/torque", { enabled: true })}
        >
          Torque On
        </button>
        <button
          disabled={!owned || !torqueOn || busy}
          onClick={() => void act("/torque", { enabled: false })}
        >
          Torque Off
        </button>
        <button
          className="danger"
          disabled={!owned}
          onClick={() => void act("/stop")}
        >
          Stop & hold
        </button>
      </div>
      <p className="connection-hint">
        Sliders move the real arm. Home uses the saved Gym reset position.
        Support the arm before Torque Off.
      </p>
    </section>
  );
}
