import { Component, useEffect, useMemo, useState } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { addToGym, readResponse } from "./api";
import type { GymSession, ReconstructionResult } from "./types";
import "./styles.css";

class PreviewBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {
    /* Download remains usable if WebGL is unavailable. */
  }
  render() {
    return this.state.failed ? (
      <p className="blender-placeholder">
        3D preview is unavailable in this browser. The GLB download is still
        ready.
      </p>
    ) : (
      this.props.children
    );
  }
}

function Solid({ result }: { result: ReconstructionResult }) {
  const geometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(result.object.mesh.vertices, 3),
    );
    geometry.setIndex(result.object.mesh.faces);
    geometry.computeVertexNormals();
    return geometry;
  }, [result]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial
        color={result.object.color}
        roughness={0.6}
        flatShading
      />
    </mesh>
  );
}

function Preview({
  result,
  activeTab,
}: {
  result: ReconstructionResult;
  activeTab: boolean;
}) {
  const size = Math.max(...result.metadata.dimensions_m);
  return (
    <PreviewBoundary key={result.object.id}>
      <Canvas
        frameloop={activeTab ? "always" : "never"}
        camera={{
          position: [size * 1.7, -size * 2.2, size * 1.3],
          up: [0, 0, 1],
          near: 0.001,
          far: 20,
          fov: 38,
        }}
        fallback={<p>WebGL unavailable. Download your GLB below.</p>}
      >
        <color attach="background" args={["#101b24"]} />
        <ambientLight intensity={1.5} />
        <directionalLight position={[2, -3, 5]} intensity={3} />
        <directionalLight position={[-2, 1, 0]} intensity={1.2} />
        <Solid result={result} />
        <OrbitControls
          makeDefault
          minDistance={size * 0.7}
          maxDistance={size * 8}
        />
        <axesHelper args={[size * 0.7]} />
      </Canvas>
    </PreviewBoundary>
  );
}

function download(result: ReconstructionResult) {
  const bytes = Uint8Array.from(atob(result.glb_base64), (c) =>
    c.charCodeAt(0),
  );
  const url = URL.createObjectURL(
    new Blob([bytes], { type: "model/gltf-binary" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = result.filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function BlenderTab({
  sessionId,
  activeTab = true,
}: {
  sessionId?: string;
  activeTab?: boolean;
}) {
  const [file, setFile] = useState<{ name: string; data: string } | null>(null);
  const [name, setName] = useState("Image object");
  const [mode, setMode] = useState<"extrude" | "revolve">("extrude");
  const [foreground, setForeground] = useState<"dark" | "light" | "alpha">(
    "dark",
  );
  const [threshold, setThreshold] = useState(128);
  const [width, setWidth] = useState(100);
  const [height, setHeight] = useState(100);
  const [depth, setDepth] = useState(30);
  const [result, setResult] = useState<ReconstructionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [sessions, setSessions] = useState<GymSession[]>([]);
  const [selected, setSelected] = useState("");
  const [sessionError, setSessionError] = useState("");
  const selectedSession = sessions.find((s) => s.sessionId === selected);

  useEffect(() => {
    setResult(null);
    setNotice("");
  }, [file, name, mode, foreground, threshold, width, height, depth]);
  async function refreshSessions() {
    setSessionError("");
    try {
      setSessions(await readResponse(await fetch("/api/sessions")));
    } catch (e) {
      setSessionError((e as Error).message);
    }
  }
  useEffect(() => {
    void refreshSessions();
  }, []);

  async function chooseFile(input?: File) {
    if (!input) return;
    setError("");
    setResult(null);
    setNotice("");
    setFile(null);
    if (input.size > 6_000_000 || !/\.(png|jpe?g)$/i.test(input.name)) {
      setError("Choose a PNG or JPEG image no larger than 6 MB.");
      return;
    }
    setBusy(true);
    try {
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(Error("The image could not be read"));
        reader.readAsDataURL(input);
      });
      setFile({ name: input.name, data });
      setName(
        input.name.replace(/\.[^.]+$/, "").slice(0, 80) || "Image object",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function generate(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    setResult(null);
    try {
      const created = await readResponse(
        await fetch("/api/blender/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            image_base64: file.data.split(",")[1],
            filename: file.name.slice(0, 120),
            name,
            mode,
            foreground,
            threshold,
            width_m: width / 1000,
            height_m: height / 1000,
            depth_m: depth / 1000,
          }),
        }),
      );
      setResult(created);
      void refreshSessions();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function add() {
    if (!result || !selectedSession) return;
    setAdding(true);
    setError("");
    setNotice("");
    try {
      await addToGym(selected, result.object);
      setNotice(
        `Added “${result.object.name}” to ${selectedSession.name}. Open Gym to position it.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdding(false);
      void refreshSessions();
    }
  }

  return (
    <main className="blender-module">
      <header className="blender-header">
        <div>
          <span className="blender-eyebrow">LOCAL OBJECT WORKSHOP</span>
          <h1>Blender</h1>
          <p>Turn a clear silhouette into a simple 3D object.</p>
        </div>
        <span className="blender-badge">Images stay on this computer</span>
      </header>
      <p className="blender-intro">
        This is an approximate shape from one image. Choose a plain background
        and enter the real dimensions. Hidden surfaces and texture are not
        recovered. Export works with Blender without installing the desktop app.
      </p>
      <div className="blender-layout">
        <form className="blender-card blender-controls" onSubmit={generate}>
          <fieldset disabled={busy || adding}>
            <h2>
              <span>1</span> Choose an image
            </h2>
            <label className="blender-upload">
              PNG or JPEG · up to 6 MB
              <input
                aria-label="Object image"
                type="file"
                accept="image/png,image/jpeg"
                onChange={(e) => void chooseFile(e.target.files?.[0])}
              />
            </label>
            {file ? (
              <div className="blender-source">
                <img src={file.data} alt="Source object" />
                <span>{file.name}</span>
              </div>
            ) : (
              <div className="blender-empty-image">
                A front-on photo or silhouette works best.
                <br />
                Leave some background around the object.
              </div>
            )}
            <label>
              Object name
              <input
                value={name}
                maxLength={80}
                required
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <h2>
              <span>2</span> Shape and size
            </h2>
            <label>
              Method
              <select
                aria-label="Method"
                value={mode}
                onChange={(e) => setMode(e.target.value as typeof mode)}
              >
                <option value="extrude">Silhouette extrusion</option>
                <option value="revolve">Revolve a symmetric object</option>
              </select>
            </label>
            <p className="blender-help">
              {mode === "extrude"
                ? "Give the image outline an even depth. Visible holes pass through the solid."
                : "Rotate a front-on outer profile around its vertical centre. Makes a solid shape; handles and cavities are not recovered."}
            </p>
            <div className="blender-dimensions">
              <label>
                {mode === "revolve" ? "Diameter" : "Width"} (mm)
                <input
                  type="number"
                  min={5}
                  max={1000}
                  step={1}
                  required
                  value={width || ""}
                  onChange={(e) => setWidth(Number(e.target.value))}
                />
              </label>
              <label>
                Height (mm)
                <input
                  type="number"
                  min={5}
                  max={1000}
                  step={1}
                  required
                  value={height || ""}
                  onChange={(e) => setHeight(Number(e.target.value))}
                />
              </label>
              {mode === "extrude" && (
                <label>
                  Depth (mm)
                  <input
                    type="number"
                    min={5}
                    max={1000}
                    step={1}
                    required
                    value={depth || ""}
                    onChange={(e) => setDepth(Number(e.target.value))}
                  />
                </label>
              )}
            </div>
            <label>
              Foreground
              <select
                aria-label="Foreground"
                value={foreground}
                onChange={(e) =>
                  setForeground(e.target.value as typeof foreground)
                }
              >
                <option value="dark">Dark object on a light background</option>
                <option value="light">Light object on a dark background</option>
                <option value="alpha">
                  Opaque object on a transparent background
                </option>
              </select>
            </label>
            <label>
              Threshold <output>{threshold}</output>
              <input
                type="range"
                min={0}
                max={255}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
              />
            </label>
            <p className="blender-help">
              The largest connected shape is used. Fine detail is simplified to
              keep the object portable.
            </p>
            <button
              className="blender-primary"
              type="submit"
              disabled={!file || busy}
            >
              {busy ? "Creating solid…" : "Create 3D object"}
            </button>
          </fieldset>
        </form>
        <section className="blender-card blender-result">
          <h2>
            <span>3</span> Inspect and use
          </h2>
          <div className="blender-preview" aria-label="3D object preview">
            {result ? (
              <Preview result={result} activeTab={activeTab} />
            ) : (
              <div className="blender-placeholder">
                <div className="blender-placeholder-cube">◇</div>
                <strong>Your solid appears here</strong>
                <p>
                  Upload an image, choose a method,
                  <br />
                  then create your 3D object.
                </p>
              </div>
            )}
          </div>
          {result && (
            <>
              <div className="blender-result-meta">
                <img
                  src={`data:image/png;base64,${result.metadata.mask_png_base64}`}
                  alt="Detected silhouette: white is the object"
                />
                <div>
                  <strong>{result.object.name}</strong>
                  <p>
                    {result.metadata.dimensions_m
                      .map((v) => `${Math.round(v * 1000)}`)
                      .join(" × ")}{" "}
                    mm · {result.metadata.triangles.toLocaleString()} triangles
                  </p>
                  <p>Closed solid · Drag to orbit · Scroll to zoom</p>
                </div>
              </div>
              <div className="blender-warnings">
                {result.metadata.warnings.map((w) => (
                  <p key={w}>{w}</p>
                ))}
              </div>
              <button type="button" onClick={() => download(result)}>
                Download Blender-compatible GLB
              </button>
            </>
          )}
          <div className="blender-gym-import">
            <label>
              Add to Gym session
              <select
                aria-label="Gym session"
                value={selected}
                disabled={adding}
                onChange={(e) => {
                  setSelected(e.target.value);
                  setNotice("");
                }}
              >
                <option value="">Choose a session explicitly…</option>
                {sessions.map((s) => (
                  <option key={s.sessionId} value={s.sessionId}>
                    {s.name} · {s.sessionId.slice(0, 8)}
                    {s.sessionId === sessionId ? " · current Gym" : ""}
                    {s.running ? " · running" : ""}
                  </option>
                ))}
              </select>
            </label>
            <div className="blender-actions">
              <button
                type="button"
                onClick={() => void refreshSessions()}
                disabled={adding}
              >
                Refresh sessions
              </button>
              <button
                type="button"
                className="blender-primary"
                disabled={!result || !selectedSession || adding || busy}
                onClick={() => void add()}
              >
                {adding ? "Adding…" : "Add to selected Gym"}
              </button>
            </div>
            <p className="blender-help">
              Pause the chosen Gym before adding. The object is placed on that
              session’s table; use Gym to adjust its position.
            </p>
            {!sessions.length && (
              <p className="blender-help">
                Open Gym to create a session, then refresh this list.
              </p>
            )}
            {sessionError && <p className="blender-error">{sessionError}</p>}
          </div>
        </section>
      </div>
      {error && (
        <p className="blender-error blender-feedback" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="blender-success blender-feedback" role="status">
          {notice}
        </p>
      )}
    </main>
  );
}
