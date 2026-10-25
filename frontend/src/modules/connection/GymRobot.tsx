import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Cable, ShieldCheck, Square, X } from "lucide-react";
import {
  api,
  jointNames,
  type CalibrationJoint,
  type ConnectionStatus,
} from "./api";
import "./connection.css";
import ManualControls from "./ManualControls";
import CartesianControls from "./CartesianControls";
import EpisodeSummary from "./EpisodeSummary";
import type { RobotControlProps } from "../types";
const executionLabels: Record<string, string> = {
  preparing: "Checking real path",
  running: "Moving to tool goals",
  waiting: "Catching up",
  paused: "Paused",
  completed: "Tool goals reached",
};

export default function GymRobot({ sessionId }: RobotControlProps) {
  const sid = sessionId || "";
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<ConnectionStatus | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [port, setPort] = useState("");
  const [calOpen, setCalOpen] = useState(false),
    [confirmed, setConfirmed] = useState(false),
    [draft, setDraft] = useState<CalibrationJoint[]>(() =>
      jointNames.map((name) => ({
        name,
        zero_raw: NaN,
        direction: 1,
        raw_min: 0,
        raw_max: 4095,
        radians_per_tick: (2 * Math.PI) / 4096,
      })),
    );
  const [notice, setNotice] = useState("");
  const current = useRef(status);
  current.current = status;
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const refreshStatus = async () => {
    const s = await api<ConnectionStatus>("/status");
    setStatus(s);
    return s;
  };
  const inventory = async () => {
    const settings = await api<{
      robot_port: string | null;
      calibration?: { joints: CalibrationJoint[] };
    }>("/settings");
    setPort(settings.robot_port || "");
    if (settings.calibration?.joints) setDraft(settings.calibration.joints);
    await refreshStatus();
  };
  useEffect(() => {
    void run(inventory);
    let stopped = false;
    let heartbeatAt = 0;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const s = current.current;
        if (
          document.visibilityState === "visible" &&
          !stopped &&
          s?.connected &&
          (s.enabled ||
            s.sync_mode !== "off" ||
            s.gym_execution?.phase === "preparing") &&
          s.owner_session_id === sid &&
          performance.now() - heartbeatAt > 700
        ) {
          await api("/heartbeat", "POST", { session_id: sid });
          heartbeatAt = performance.now();
        }
        if (!stopped) await refreshStatus();
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!stopped) timer = setTimeout(poll, open ? 80 : 700);
      }
    };
    timer = setTimeout(poll, open ? 80 : 700);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
    // sid changes must renew the lease only for the selected owner.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sid, open]);
  useEffect(() => {
    const stopHidden = () => {
      const state = current.current;
      if (
        !state?.connected ||
        state.owner_session_id !== sid ||
        (!state.enabled &&
          state.sync_mode === "off" &&
          state.gym_execution?.phase !== "preparing")
      )
        return;
      // Keep internal Gym navigation usable; leaving the browser ends physical control.
      void fetch("/api/connection/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid }),
        keepalive: true,
      })
        .then(async (response) => {
          if (!response.ok)
            throw new Error(
              "Stop request could not be confirmed; controller lease will expire.",
            );
          setStatus(await response.json());
        })
        .catch((error) => setError(String(error)));
    };
    const visibility = () => {
      if (document.visibilityState !== "visible") stopHidden();
    };
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", stopHidden);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", stopHidden);
      stopHidden();
    };
  }, [sid]);
  useEffect(() => {
    if (open) void run(inventory);
    // Refresh persisted configuration when opening controls from Gym.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);
  const command = (path: string, extra: Record<string, unknown> = {}) =>
    run(async () => {
      setStatus(
        await api<ConnectionStatus>(path, "POST", {
          session_id: sid,
          ...extra,
        }),
      );
    });
  const owned = !!sid && status?.owner_session_id === sid;
  const stop = () =>
    void run(async () => {
      setStatus(
        await api<ConnectionStatus>("/stop", "POST", {
          session_id: status?.owner_session_id,
        }),
      );
    });
  const updateJoint = (
    index: number,
    key: keyof CalibrationJoint,
    value: number,
  ) =>
    setDraft((old) =>
      old.map((j, i) => (i === index ? { ...j, [key]: value } : j)),
    );
  return (
    <>
      <button className="btn btn-ghost" onClick={() => setOpen(true)}>
        <Cable size={17} />
        {status?.connected ? "Robot connection" : "Connect robot"}
        {status?.connected && owned && (
          <span
            className="robot-run-state"
            title={status.gym_execution?.message}
          >
            {" "}
            ·{" "}
            {status.fault
              ? "Stopped · check connection"
              : status.limit_recovery_active
                ? "Returning inside limits"
                : status.limit_violations?.length
                  ? "Joint limit · check controls"
                  : executionLabels[status.gym_execution?.phase || "idle"] ||
                    "Ready for real run"}
          </span>
        )}
      </button>
      {status?.fault && owned && (
        <div role="alert">
          <button className="robot-fault-banner" onClick={() => setOpen(true)}>
            Robot stopped · {status.fault}
          </button>
        </div>
      )}
      {open &&
        createPortal(
          <div className="robot-dialog-backdrop" onClick={() => setOpen(false)}>
            <div
              className="connection-page robot-dialog"
              role="dialog"
              aria-modal="true"
              aria-label="Robot connection"
              onClick={(e) => e.stopPropagation()}
            >
              <header className="connection-heading">
                <div>
                  <p className="connection-eyebrow">GYM / REAL ARM</p>
                  <h1>Robot connection</h1>
                  <p>
                    Run simulation tests the task without moving the arm. After
                    it succeeds, Run Realrobot checks the measured starting pose
                    and runs the real arm.
                  </p>
                </div>
                <button
                  aria-label="Close robot controls"
                  onClick={() => setOpen(false)}
                >
                  <X size={20} />
                </button>
              </header>
              {error && (
                <div role="alert" className="connection-error">
                  {error}
                </div>
              )}
              {notice && (
                <div role="status" className="connection-notice">
                  {notice}
                </div>
              )}
              {status?.connected && status.tool && (
                <CartesianControls
                  sid={sid}
                  status={status}
                  owned={owned}
                  onError={setError}
                  refresh={refreshStatus}
                />
              )}
              {status?.connected && (
                <ManualControls
                  sid={sid}
                  status={status}
                  owned={owned}
                  onError={setError}
                  refresh={refreshStatus}
                />
              )}
              <div className="connection-grid">
                <section className="connection-card">
                  <h2>
                    <Cable size={19} /> SO-101 arm{" "}
                    <span
                      className={`connection-badge ${status?.connected ? "ok" : ""}`}
                    >
                      {status?.connected ? "Connected" : "Disconnected"}
                    </span>
                  </h2>
                  <p className="connection-hint">
                    Serial port:{" "}
                    {port || "Choose and save a port in Setting Connection."}
                  </p>
                  {status?.connected && !owned && (
                    <p className="connection-error">
                      Another Gym scene owns the robot. Disconnect it before
                      connecting this scene.
                    </p>
                  )}
                  <div className="connection-actions">
                    <button
                      className="primary"
                      disabled={busy || !port || !sid || !!status?.connected}
                      onClick={() =>
                        void run(async () => {
                          await api<ConnectionStatus>("/connect", "POST", {
                            session_id: sid,
                            port,
                          });
                          await refreshStatus();
                        })
                      }
                    >
                      Connect robot
                    </button>
                    <button
                      disabled={busy || !status?.connected}
                      onClick={() =>
                        void command("/disconnect", {
                          session_id: status?.owner_session_id,
                        })
                      }
                    >
                      Disconnect
                    </button>
                  </div>
                  <p className="connection-hint">
                    Connect reads the arm without moving it. Use Tool position
                    or Run Realrobot to move after checking the target.
                  </p>
                  {status?.identity && (
                    <p className="connection-device-id">
                      Device:{" "}
                      {typeof status.identity === "string"
                        ? status.identity
                        : JSON.stringify(status.identity)}
                    </p>
                  )}
                  {status?.connected && (
                    <>
                      <div className="connection-verify">
                        <ShieldCheck size={17} />
                        {status.calibrated
                          ? "Joint mapping verified"
                          : "Joint mapping required before movement"}
                      </div>
                      <button
                        disabled={
                          !owned ||
                          busy ||
                          status.enabled ||
                          status.sync_mode !== "off"
                        }
                        onClick={() => {
                          setCalOpen(!calOpen);
                          setConfirmed(false);
                        }}
                      >
                        Edit joint mapping
                      </button>
                    </>
                  )}
                </section>
                <section className="connection-card">
                  <h2>
                    Joint diagnostics{" "}
                    <span
                      className={`connection-badge ${status?.enabled ? "ok" : ""}`}
                    >
                      {status?.enabled ? "Enabled" : "Read only"}
                    </span>
                  </h2>
                  <p className="connection-hint">
                    Optional joint synchronization for diagnostics. Run
                    Realrobot uses tool goals independently of Gym joint angles.
                  </p>
                  <div className="connection-actions">
                    <button
                      disabled={
                        busy ||
                        !owned ||
                        !status?.calibrated ||
                        !!status?.enabled ||
                        status?.sync_mode !== "off"
                      }
                      onClick={() => void command("/align")}
                    >
                      Match Gym to real arm
                    </button>
                    <button
                      className="primary"
                      disabled={
                        busy ||
                        !owned ||
                        !status?.calibrated ||
                        !!status?.enabled
                      }
                      onClick={() => void command("/enable")}
                    >
                      Enable at current pose
                    </button>
                    <button
                      disabled={
                        busy ||
                        !owned ||
                        !status?.calibrated ||
                        !!status?.enabled ||
                        status?.sync_mode !== "off"
                      }
                      title="Only for a shallow jaw/table overlap in an empty scene. Checks the entire separating path."
                      onClick={() => void command("/retreat")}
                    >
                      Lift clear of table
                    </button>
                    <button
                      className="connection-stop"
                      disabled={!status?.connected}
                      onClick={stop}
                    >
                      <Square size={14} /> Stop & hold
                    </button>
                  </div>
                  <label>
                    Realtime direction
                    <select
                      aria-label="Realtime direction"
                      disabled={
                        busy ||
                        !owned ||
                        !status?.calibrated ||
                        !!status.manual_target
                      }
                      value={status?.sync_mode || "off"}
                      onChange={(e) =>
                        void command("/sync", { mode: e.target.value })
                      }
                    >
                      <option value="off">Off</option>
                      <option value="real_to_gym">Real arm → Gym</option>
                      <option value="gym_to_real">Gym → Real arm</option>
                    </select>
                  </label>
                  <p className="connection-hint">
                    First match Gym to the measured arm pose, then enable
                    movement and choose Gym → Real arm.
                  </p>
                  <p className="connection-hint">
                    Stop & hold keeps motor torque. It is not a physical
                    emergency power switch. Reconnection never resumes motion
                    automatically.
                  </p>
                  {status?.fault && (
                    <p className="connection-error">{status.fault}</p>
                  )}
                  <div className="connection-metrics">
                    <span>
                      Largest angle error{" "}
                      <strong>
                        {status?.sync_mode !== "gym_to_real" ||
                        !status.tracking_error_rad
                          ? "—"
                          : `${((Math.max(...status.tracking_error_rad.map(Math.abs)) * 180) / Math.PI).toFixed(2)}°`}
                      </strong>
                    </span>
                    <span>
                      Feedback age{" "}
                      <strong>
                        {status?.telemetry_age_s == null
                          ? "—"
                          : `${(status.telemetry_age_s * 1000).toFixed(0)} ms`}
                      </strong>
                    </span>
                    <span>
                      Owner{" "}
                      <strong>
                        {status?.owner_session_id?.slice(0, 8) || "—"}
                      </strong>
                    </span>
                    <span>
                      Temperature rechecks{" "}
                      <strong>{status?.temperature_rechecks ?? 0}</strong>
                    </span>
                  </div>
                </section>
              </div>
              {status?.gym_execution?.report?.session_id === sid && (
                <EpisodeSummary report={status.gym_execution.report} />
              )}
              {calOpen && (
                <section className="connection-card connection-calibration">
                  <h2>Joint mapping</h2>
                  <p>
                    Enter the encoder reading for each joint at the simulation
                    zero angle. Check rotation direction and mechanical limits
                    for your arm. Values are stored locally; motor EEPROM is
                    never changed.
                  </p>
                  <div className="connection-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Joint</th>
                          <th>Zero encoder</th>
                          <th>Direction</th>
                          <th>Min encoder</th>
                          <th>Max encoder</th>
                          <th>Radians / tick</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draft.map((j, i) => (
                          <tr key={j.name}>
                            <th>{j.name}</th>
                            <td>
                              <input
                                aria-label={`${j.name} zero`}
                                type="number"
                                step="any"
                                value={
                                  Number.isNaN(j.zero_raw) ? "" : j.zero_raw
                                }
                                onChange={(e) =>
                                  updateJoint(
                                    i,
                                    "zero_raw",
                                    e.target.value === ""
                                      ? NaN
                                      : Number(e.target.value),
                                  )
                                }
                              />
                            </td>
                            <td>
                              <select
                                value={j.direction}
                                onChange={(e) =>
                                  updateJoint(
                                    i,
                                    "direction",
                                    Number(e.target.value),
                                  )
                                }
                              >
                                <option value={1}>+1</option>
                                <option value={-1}>−1</option>
                              </select>
                            </td>
                            <td>
                              <input
                                aria-label={`${j.name} minimum`}
                                type="number"
                                value={j.raw_min}
                                onChange={(e) =>
                                  updateJoint(
                                    i,
                                    "raw_min",
                                    Number(e.target.value),
                                  )
                                }
                              />
                            </td>
                            <td>
                              <input
                                aria-label={`${j.name} maximum`}
                                type="number"
                                value={j.raw_max}
                                onChange={(e) =>
                                  updateJoint(
                                    i,
                                    "raw_max",
                                    Number(e.target.value),
                                  )
                                }
                              />
                            </td>
                            <td>
                              <input
                                aria-label={`${j.name} radians per tick`}
                                type="number"
                                step="0.000001"
                                value={j.radians_per_tick}
                                onChange={(e) =>
                                  updateJoint(
                                    i,
                                    "radians_per_tick",
                                    Number(e.target.value),
                                  )
                                }
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <label className="connection-checkbox">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      onChange={(e) => setConfirmed(e.target.checked)}
                    />{" "}
                    I have checked these zero angles, directions and limits
                    against this physical arm.
                  </label>
                  <button
                    className="primary"
                    disabled={
                      busy ||
                      !confirmed ||
                      draft.some((j) => !Number.isFinite(j.zero_raw))
                    }
                    onClick={() =>
                      void run(async () => {
                        setStatus(
                          await api<ConnectionStatus>("/calibration", "PUT", {
                            session_id: sid,
                            identity: status?.identity,
                            confirmed,
                            joints: draft,
                          }),
                        );
                        setCalOpen(false);
                        setNotice("Joint mapping saved for this device.");
                      })
                    }
                  >
                    Save verified mapping
                  </button>
                </section>
              )}
              <section className="connection-card">
                <h2>Motor feedback & small moves</h2>
                <p className="connection-hint">
                  Jog ±1° at a time. Movement requires verified mapping, enabled
                  motors, and a collision-safe matching Gym scene.
                </p>
                <div className="connection-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Joint</th>
                        <th>Encoder</th>
                        <th>Measured angle</th>
                        <th>Gym target</th>
                        <th>Difference</th>
                        <th>Voltage</th>
                        <th>Temperature</th>
                        <th>Torque</th>
                        <th>Jog</th>
                      </tr>
                    </thead>
                    <tbody>
                      {jointNames.map((name, i) => {
                        const t = status?.telemetry?.find(
                          (t) => t.name === name,
                        );
                        return (
                          <tr key={name}>
                            <th>{name.replaceAll("_", " ")}</th>
                            <td>{t?.raw ?? "—"}</td>
                            <td>
                              {t?.position_rad == null
                                ? "Unmapped"
                                : `${((t.position_rad * 180) / Math.PI).toFixed(1)}°`}
                            </td>
                            <td>
                              {status?.sync_mode === "gym_to_real" &&
                              status.desired_rad
                                ? `${((status.desired_rad[i] * 180) / Math.PI).toFixed(2)}°`
                                : "—"}
                            </td>
                            <td>
                              {status?.sync_mode === "gym_to_real" &&
                              status.tracking_error_rad
                                ? `${((status.tracking_error_rad[i] * 180) / Math.PI).toFixed(2)}°`
                                : "—"}
                            </td>
                            <td>{t ? `${t.voltage.toFixed(1)} V` : "—"}</td>
                            <td>{t ? `${t.temperature} °C` : "—"}</td>
                            <td>{t ? (t.torque ? "On" : "Off") : "—"}</td>
                            <td>
                              <button
                                aria-label={`Jog ${name} minus`}
                                disabled={
                                  busy ||
                                  !owned ||
                                  !status?.enabled ||
                                  !!status.manual_target ||
                                  !!status.limit_recovery_active ||
                                  status.sync_mode !== "off"
                                }
                                onClick={() =>
                                  void command("/jog", {
                                    joint: i,
                                    delta_rad: -Math.PI / 180,
                                  })
                                }
                              >
                                −1°
                              </button>
                              <button
                                aria-label={`Jog ${name} plus`}
                                disabled={
                                  busy ||
                                  !owned ||
                                  !status?.enabled ||
                                  !!status.manual_target ||
                                  !!status.limit_recovery_active ||
                                  status.sync_mode !== "off"
                                }
                                onClick={() =>
                                  void command("/jog", {
                                    joint: i,
                                    delta_rad: Math.PI / 180,
                                  })
                                }
                              >
                                +1°
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>,
          document.body,
        )}
      {status?.connected &&
        (status.enabled || status.sync_mode !== "off") &&
        createPortal(
          <button className="connection-global-stop" onClick={stop}>
            <Square size={16} /> Real arm · Stop & hold
          </button>,
          document.body,
        )}
    </>
  );
}
