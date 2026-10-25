import { useEffect, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
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
  const preview = status.robot_preview;
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
        <div className="manual-model" aria-label="Live measured SO-101 model">
          {preview ? (
            <Canvas
              camera={{ position: [0.5, -0.65, 0.4], up: [0, 0, 1], fov: 40 }}
            >
              <ambientLight intensity={1.5} />
              <directionalLight position={[1, -1, 2]} intensity={2} />
              <mesh position={[0, 0, -0.015]}>
                <boxGeometry args={[0.12, 0.1, 0.03]} />
                <meshStandardMaterial color="#384b50" />
              </mesh>
              <Line points={preview.points} color="#efc842" lineWidth={12} />
              {preview.points.map((p, i) => (
                <mesh key={i} position={p}>
                  <sphereGeometry args={[0.013, 16, 12]} />
                  <meshStandardMaterial color="#33464c" />
                </mesh>
              ))}
              {preview.fingers.map((p, i) => (
                <Line
                  key={i}
                  points={[preview.points[preview.points.length - 1], p]}
                  color="#efc842"
                  lineWidth={6}
                />
              ))}
              <OrbitControls
                target={[0, 0, 0.15]}
                enablePan={false}
                minDistance={0.3}
                maxDistance={1.5}
              />
            </Canvas>
          ) : (
            <p>Connect to view measured pose</p>
          )}
          <span>Encoder feedback · simplified model</span>
        </div>
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
