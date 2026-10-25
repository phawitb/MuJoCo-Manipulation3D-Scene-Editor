import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Cable, Camera, RefreshCw, ShieldCheck, Square } from "lucide-react";
import {
  api,
  jointNames,
  type Assignments,
  type CalibrationJoint,
  type ConnectionStatus,
} from "./api";
import "./connection.css";
type Session = { sessionId: string; name: string };
type Port = { device?: string; port?: string; description?: string };
type CameraResult = { index: number; available: boolean; error?: string };
export default function ConnectionTab({
  activeTab = true,
}: {
  activeTab?: boolean;
}) {
  const [status, setStatus] = useState<ConnectionStatus | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [ports, setPorts] = useState<Port[]>([]),
    [port, setPort] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]),
    [sid, setSid] = useState(
      () => new URLSearchParams(location.search).get("session") || "",
    );
  const [cameras, setCameras] = useState<CameraResult[]>([]),
    [scanMax, setScanMax] = useState(5),
    [assign, setAssign] = useState<Assignments>({
      back: null,
      front: null,
      wrist: null,
    });
  const [preview, setPreview] = useState<number | null>(null),
    [frame, setFrame] = useState(""),
    [frameError, setFrameError] = useState("");
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
    if (s.port) setPort(s.port);
    return s;
  };
  const inventory = async () => {
    const [p, r, settings] = await Promise.all([
      api<Port[] | { ports: Port[] }>("/ports"),
      fetch("/api/sessions"),
      api<{
        assignments: Assignments;
        calibration?: { joints: CalibrationJoint[] };
      }>("/settings"),
    ]);
    const ps = Array.isArray(p) ? p : p.ports;
    setPorts(ps);
    if (!port && ps.length === 1) setPort(ps[0].device || ps[0].port || "");
    if (!r.ok) throw new Error("Cannot list Gym sessions");
    setSessions(await r.json());
    setAssign(settings.assignments);
    if (settings.calibration?.joints) setDraft(settings.calibration.joints);
    await refreshStatus();
  };
  useEffect(() => {
    void run(inventory);
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const s = current.current;
        if (
          document.visibilityState === "visible" &&
          !stopped &&
          s?.connected &&
          (s.enabled || s.sync_mode !== "off") &&
          s.owner_session_id === sid
        )
          await api("/heartbeat", "POST", { session_id: sid });
        if (!stopped) await refreshStatus();
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!stopped) timer = setTimeout(poll, 700);
      }
    };
    timer = setTimeout(poll, 700);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
    // sid changes must renew the lease only for the selected owner.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sid]);
  useEffect(() => {
    const stopHidden = () => {
      const state = current.current;
      if (
        !state?.connected ||
        state.owner_session_id !== sid ||
        (!state.enabled && state.sync_mode === "off")
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
    };
  }, [sid]);
  useEffect(() => {
    if (preview === null || !activeTab) return;
    let stopped = false,
      url = "";
    let timer: ReturnType<typeof setTimeout>;
    const capture = async () => {
      try {
        const r = await fetch(`/api/connection/cameras/${preview}/frame`);
        if (!r.ok) throw new Error((await r.text()).slice(0, 180));
        const blob = await r.blob();
        if (!stopped) {
          if (url) URL.revokeObjectURL(url);
          url = URL.createObjectURL(blob);
          setFrame(url);
          setFrameError("");
        }
      } catch (e) {
        if (!stopped) setFrameError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!stopped) timer = setTimeout(capture, 700);
      }
    };
    setFrame("");
    void capture();
    return () => {
      stopped = true;
      clearTimeout(timer);
      if (url) URL.revokeObjectURL(url);
    };
  }, [preview, activeTab]);
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
    <main className="connection-page">
      <header className="connection-heading">
        <div>
          <p className="connection-eyebrow">REAL WORLD / LOCAL DEVICES</p>
          <h1>Setting Connection</h1>
          <p>
            Connect your SO-101 and choose the cameras around your workspace.
          </p>
        </div>
        <button onClick={() => void run(inventory)} disabled={busy}>
          <RefreshCw size={16} /> Refresh devices
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
          <label>
            Gym session
            <select
              aria-label="Hardware Gym session"
              value={sid}
              disabled={busy}
              onChange={(e) => setSid(e.target.value)}
            >
              <option value="">Choose a scene session</option>
              {sessions.map((s) => (
                <option key={s.sessionId} value={s.sessionId}>
                  {s.name} · {s.sessionId.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          {!sessions.length && (
            <button
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  const r = await fetch("/api/sessions", { method: "POST" });
                  if (!r.ok) throw new Error("Could not create session");
                  const s = await r.json();
                  setSid(s.sessionId);
                  await inventory();
                })
              }
            >
              Create a device workspace
            </button>
          )}
          <label>
            Serial port
            <input
              aria-label="Serial port"
              list="serial-ports"
              value={port}
              disabled={!!status?.connected}
              onChange={(e) => setPort(e.target.value)}
              placeholder="/dev/cu.usbmodem…"
            />
            <datalist id="serial-ports">
              {ports.map((p) => (
                <option key={p.device || p.port} value={p.device || p.port}>
                  {p.description}
                </option>
              ))}
            </datalist>
          </label>
          <div className="connection-actions">
            <button
              className="primary"
              disabled={busy || !port || !sid || !!status?.connected}
              onClick={() => void command("/connect", { port })}
            >
              Connect & verify
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
            Connecting reads the six motors. It does not enable movement or
            change motor calibration.
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
                  !owned || busy || status.enabled || status.sync_mode !== "off"
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
            Live motion{" "}
            <span className={`connection-badge ${status?.enabled ? "ok" : ""}`}>
              {status?.enabled ? "Enabled" : "Read only"}
            </span>
          </h2>
          <p className="connection-hint">
            Use measured angles to match Gym, or send Gym motion to the real
            arm. The connection stops streaming if feedback or the controller
            heartbeat is lost.
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
                busy || !owned || !status?.calibrated || !!status?.enabled
              }
              onClick={() => void command("/enable")}
            >
              Enable at current pose
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
              disabled={busy || !owned || !status?.calibrated}
              value={status?.sync_mode || "off"}
              onChange={(e) => void command("/sync", { mode: e.target.value })}
            >
              <option value="off">Off</option>
              <option value="real_to_gym">Real arm → Gym</option>
              <option value="gym_to_real">Gym → Real arm</option>
            </select>
          </label>
          <p className="connection-hint">
            First match Gym to the measured arm pose, then enable movement and
            choose Gym → Real arm.
          </p>
          <p className="connection-hint">
            Stop & hold keeps motor torque. It is not a physical emergency power
            switch. Reconnection never resumes motion automatically.
          </p>
          {status?.fault && <p className="connection-error">{status.fault}</p>}
          <div className="connection-metrics">
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
              <strong>{status?.owner_session_id?.slice(0, 8) || "—"}</strong>
            </span>
          </div>
        </section>
      </div>
      {calOpen && (
        <section className="connection-card connection-calibration">
          <h2>Joint mapping</h2>
          <p>
            Enter the encoder reading for each joint at the simulation zero
            angle. Check rotation direction and mechanical limits for your arm.
            Values are stored locally; motor EEPROM is never changed.
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
                        value={Number.isNaN(j.zero_raw) ? "" : j.zero_raw}
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
                          updateJoint(i, "direction", Number(e.target.value))
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
                          updateJoint(i, "raw_min", Number(e.target.value))
                        }
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`${j.name} maximum`}
                        type="number"
                        value={j.raw_max}
                        onChange={(e) =>
                          updateJoint(i, "raw_max", Number(e.target.value))
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
            I have checked these zero angles, directions and limits against this
            physical arm.
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
          Jog ±1° at a time. Movement requires verified mapping, enabled motors,
          and a collision-safe matching Gym scene.
        </p>
        <div className="connection-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Joint</th>
                <th>Encoder</th>
                <th>Measured angle</th>
                <th>Voltage</th>
                <th>Temperature</th>
                <th>Torque</th>
                <th>Jog</th>
              </tr>
            </thead>
            <tbody>
              {jointNames.map((name, i) => {
                const t = status?.telemetry?.find((t) => t.name === name);
                return (
                  <tr key={name}>
                    <th>{name.replaceAll("_", " ")}</th>
                    <td>{t?.raw ?? "—"}</td>
                    <td>
                      {t?.position_rad == null
                        ? "Unmapped"
                        : `${((t.position_rad * 180) / Math.PI).toFixed(1)}°`}
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
      <section className="connection-card">
        <h2>
          <Camera size={19} /> Workspace cameras
        </h2>
        <p className="connection-hint">
          Scan local camera indices, preview each source, then assign Back,
          Front and Wrist. Allow camera access in macOS if prompted.
        </p>
        <div className="connection-actions">
          <label>
            Indices to check
            <input
              aria-label="Camera scan count"
              type="number"
              min={1}
              max={8}
              value={scanMax}
              onChange={(e) => setScanMax(Number(e.target.value))}
            />
          </label>
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                setPreview(null);
                const r = await api<{
                  cameras: CameraResult[];
                  assignments: Assignments;
                }>("/cameras/scan", "POST", { max_index: scanMax - 1 });
                setCameras(r.cameras);
                setAssign(r.assignments);
                setNotice(
                  `Found ${r.cameras.filter((c) => c.available).length} available cameras.`,
                );
              })
            }
          >
            Scan & verify cameras
          </button>
        </div>
        <div className="connection-camera-grid">
          {cameras.map((c) => (
            <button
              className={`connection-camera ${preview === c.index ? "selected" : ""}`}
              key={c.index}
              disabled={!c.available}
              onClick={() => setPreview(c.index)}
            >
              <Camera size={22} />
              <strong>idx {c.index}</strong>
              <span>
                {c.available ? "Preview camera" : c.error || "Unavailable"}
              </span>
            </button>
          ))}
        </div>
        {preview !== null && (
          <div className="connection-preview">
            <div>
              <strong>Camera idx {preview}</strong>
              <button
                onClick={() => {
                  setPreview(null);
                  setFrame("");
                }}
              >
                Close preview
              </button>
            </div>
            {frame && <img src={frame} alt={`Live camera ${preview}`} />}
            <p>
              {frameError ||
                (!frame ? "Waiting for camera…" : "Refreshed local snapshot")}
            </p>
          </div>
        )}
        <div className="connection-assignments">
          {(["back", "front", "wrist"] as const).map((role) => (
            <label key={role}>
              {role[0].toUpperCase() + role.slice(1)} camera idx
              <input
                aria-label={`${role} camera idx`}
                type="number"
                min={0}
                max={7}
                value={assign[role] ?? ""}
                placeholder="Unassigned"
                onChange={(e) =>
                  setAssign((a) => ({
                    ...a,
                    [role]:
                      e.target.value === "" ? null : Number(e.target.value),
                  }))
                }
              />
            </label>
          ))}
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await api("/cameras/assignments", "PUT", assign);
                setNotice(
                  "Camera assignments saved. They will be restored next launch.",
                );
              })
            }
          >
            Save camera setup
          </button>
        </div>
      </section>
      {status?.connected &&
        (status.enabled || status.sync_mode !== "off") &&
        createPortal(
          <button className="connection-global-stop" onClick={stop}>
            <Square size={16} /> Real arm · Stop & hold
          </button>,
          document.body,
        )}
    </main>
  );
}
