import { useEffect, useRef, useState } from "react";
import { Cable, Camera, RefreshCw, ShieldCheck } from "lucide-react";
import {
  api,
  type Assignments,
  type CameraResult,
  type ConnectionSettings,
  type Verification,
} from "./api";
import CameraStack from "./CameraStack";
import "./connection.css";
type Port = { port: string; description?: string };
const roles = ["back", "front", "wrist"] as const;
export default function ConnectionTab({
  activeTab = true,
}: {
  activeTab?: boolean;
}) {
  const [ports, setPorts] = useState<Port[]>([]);
  const [port, setPort] = useState("");
  const [assign, setAssign] = useState<Assignments>({
    back: null,
    front: null,
    wrist: null,
  });
  const [saved, setSaved] = useState<ConnectionSettings | null>(null);
  const [count, setCount] = useState(5);
  const [cameras, setCameras] = useState<CameraResult[]>([]);
  const verificationEpoch = useRef(0);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [view, setView] = useState<"scan" | "verify">("scan");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const run = async (name: string, fn: () => Promise<void>) => {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };
  const refreshPorts = async () => {
    const result = await api<{ ports: Port[] }>("/ports");
    setPorts(result.ports);
  };
  useEffect(() => {
    // A tab refresh may discover setup changed by another viewer or MCP.
    // Invalidate both displayed results and captures still in flight.
    verificationEpoch.current += 1;
    setVerification(null);
    if (!activeTab) return;
    let cancelled = false;
    void Promise.all([
      api<ConnectionSettings>("/settings"),
      api<{ ports: Port[] }>("/ports"),
    ])
      .then(([settings, inventory]) => {
        if (cancelled) return;
        verificationEpoch.current += 1;
        setVerification(null);
        setSaved(settings);
        setAssign(settings.assignments);
        setPorts(inventory.ports);
        setPort(
          settings.robot_port ||
            (inventory.ports.length === 1 ? inventory.ports[0].port : ""),
        );
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab]);
  const portDirty = port !== (saved?.robot_port ?? "");
  const camerasDirty = roles.some(
    (role) => assign[role] !== saved?.assignments[role],
  );
  const clearResult = () => {
    verificationEpoch.current += 1;
    setVerification(null);
  };
  return (
    <main className="connection-page">
      <header className="connection-heading">
        <div>
          <p className="connection-eyebrow">REAL WORLD / LOCAL DEVICES</p>
          <h1>Setting Connection</h1>
          <p>
            Set up your arm and camera views. Connect and move the robot in Gym.
          </p>
        </div>
      </header>
      {error && (
        <div className="connection-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="connection-notice" role="status">
          {notice}
        </div>
      )}
      <section className="connection-card">
        <h2>
          <Cable size={19} /> SO-101 arm
        </h2>
        <div className="connection-port-row">
          <label>
            Serial port
            <input
              aria-label="Serial port"
              list="serial-ports"
              value={port}
              disabled={!!busy}
              onChange={(e) => {
                setPort(e.target.value);
                clearResult();
              }}
              placeholder="/dev/cu.usbmodem…"
            />
          </label>
          <datalist id="serial-ports">
            {ports.map((p) => (
              <option key={p.port} value={p.port}>
                {p.description}
              </option>
            ))}
          </datalist>
          <button
            disabled={!!busy}
            onClick={() => void run("ports", refreshPorts)}
          >
            <RefreshCw size={16} /> Refresh ports
          </button>
          <button
            className="primary"
            disabled={!!busy || !port || !portDirty}
            onClick={() =>
              void run("save-port", async () => {
                setSaved(
                  await api<ConnectionSettings>("/port", "PUT", { port }),
                );
                clearResult();
                setNotice("Robot port saved.");
              })
            }
          >
            Save port
          </button>
        </div>
        <p className="connection-hint">
          Saving a port does not move or connect the arm. Use Connect robot in
          Gym when you are ready.
        </p>
      </section>
      <section className="connection-card">
        <h2>
          <Camera size={19} /> Workspace cameras
        </h2>
        <div className="connection-scan-row">
          <label>
            Indices to check
            <input
              aria-label="Indices to check"
              type="number"
              min={1}
              max={8}
              value={count}
              disabled={!!busy}
              onChange={(e) => setCount(Number(e.target.value))}
            />
          </label>
          <button
            disabled={
              !!busy || !Number.isInteger(count) || count < 1 || count > 8
            }
            onClick={() =>
              void run("scan", async () => {
                setView("scan");
                setCameras([]);
                setVerification(null);
                // Capture sequentially so each image appears as soon as its camera responds.
                for (let index = 0; index < count; index++) {
                  const result = await api<CameraResult>(
                    `/cameras/${index}/snapshot`,
                  );
                  setCameras((previous) => [...previous, result]);
                }
                setNotice("Scan complete. Assign the indices you want below.");
              })
            }
          >
            <Camera size={16} />
            {busy === "scan" ? "Scanning…" : "Scan"}
          </button>
          <span className="connection-hint">
            idx 0–{Math.max(0, count - 1)}
          </span>
        </div>
        {view === "scan" && <CameraStack cameras={cameras} />}
        <div className="connection-assignments">
          {roles.map((role) => (
            <label key={role}>
              {role[0].toUpperCase() + role.slice(1)} camera idx
              <input
                aria-label={`${role} camera idx`}
                type="number"
                min={0}
                max={7}
                value={assign[role] ?? ""}
                disabled={!!busy}
                placeholder="Unassigned"
                onChange={(e) => {
                  setAssign((a) => ({
                    ...a,
                    [role]:
                      e.target.value === "" ? null : Number(e.target.value),
                  }));
                  clearResult();
                }}
              />
            </label>
          ))}
          <button
            className="primary"
            disabled={!!busy || !camerasDirty}
            onClick={() =>
              void run("save-cameras", async () => {
                setSaved(
                  await api<ConnectionSettings>(
                    "/cameras/assignments",
                    "PUT",
                    assign,
                  ),
                );
                clearResult();
                setNotice("Camera setup saved for the next launch.");
              })
            }
          >
            Save camera setup
          </button>
        </div>
      </section>
      <footer className="connection-verification">
        <button
          className="primary"
          disabled={!!busy || !saved?.robot_port || portDirty || camerasDirty}
          onClick={() =>
            void run("verify", async () => {
              setView("verify");
              setVerification(null);
              const epoch = verificationEpoch.current;
              const result = await api<Verification>("/verify", "POST");
              if (epoch === verificationEpoch.current) setVerification(result);
            })
          }
        >
          <ShieldCheck size={18} />
          {busy === "verify" ? "Verifying…" : "Verify connections"}
        </button>
        <p className="connection-hint">
          {portDirty || camerasDirty
            ? "Save your changes before verifying."
            : "Check the robot and saved camera views without sending motion commands."}
        </p>
        {verification && (
          <div role="status">
            <p
              className={
                verification.robot.ok ? "connection-verify" : "connection-error"
              }
            >
              {verification.robot.ok
                ? "Robot verified · "
                : "Robot check failed · "}
              {verification.robot.message}
              {verification.robot.ok && !verification.robot.calibrated
                ? " Joint mapping is required before movement."
                : ""}
            </p>
            {verification.unassigned.length > 0 && (
              <p className="connection-hint">
                Unassigned: {verification.unassigned.join(", ")}
              </p>
            )}
            {!verification.cameras.length && (
              <p className="connection-hint">No camera views assigned.</p>
            )}
            <CameraStack cameras={verification.cameras} />
          </div>
        )}
      </footer>
    </main>
  );
}
