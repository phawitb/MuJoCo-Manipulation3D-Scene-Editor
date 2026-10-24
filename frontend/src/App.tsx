import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  ArrowUpRight,
  Bot,
  Check,
  CircleHelp,
  Columns2,
  Focus,
  Grid3X3,
  LoaderCircle,
  Magnet,
  MousePointer2,
  Move,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  SkipForward,
  X,
} from "lucide-react";
import { Library } from "./Library";
import { Inspector } from "./Inspector";
import { Viewport } from "./Viewport";
import { useSimulation } from "./useSimulation";
import {
  dropPosition,
  readCameras,
  validateDocument,
} from "./math";
import type {
  Cameras,
  ObjectPose,
  Quat,
  Scene,
  SceneObject,
  Vec3,
  ViewKind,
} from "./types";

export default function App() {
  const sim = useSimulation();
  const [selected, setSelected] = useState<string | null>(null);
  const [transform, setTransform] = useState<"translate" | "rotate">(
    "translate",
  );
  const [snap, setSnap] = useState(false),
    [grid, setGrid] = useState(true),
    [dual, setDual] = useState(true);
  const [singleView, setSingleView] = useState<ViewKind>("main"),
    [active, setActive] = useState<ViewKind>("main");
  const [frameSignal, setFrameSignal] = useState(0),
    [resetSignal] = useState(0),
    [cameraEpoch, setCameraEpoch] = useState(0);
  const [cameras, setCameras] = useState<Cameras>(readCameras);
  const cameraRef = useRef(cameras);
  const preview = useRef<ObjectPose | null>(null);
  const [toast, setToast] = useState(""),
    [help, setHelp] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const editable =
    sim.status === "connected" && !sim.state?.running && !sim.busy;
  const editableRef = useRef(editable);
  editableRef.current = editable;
  const notify = (message: string) => setToast(message);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(timer);
  }, [toast]);
  const safe = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
    } catch (e) {
      sim.setError(e instanceof Error ? e.message : String(e));
    }
  };
  const editScene = (fn: (s: Scene) => void) => {
    if (!editableRef.current) return;
    void safe(async () => {
      const scene = sim.currentScene();
      fn(scene);
      await sim.command("load", { scene });
    });
  };
  const patchObject = (id: string, patch: Partial<SceneObject>) =>
    editScene((s) => {
      const obj = s.objects.find((o) => o.id === id);
      if (obj) Object.assign(obj, patch);
    });
  const addObject = (assetId: string, hit?: Vec3) => {
    if (!editableRef.current) return;
    const asset = sim.assets.find((a) => a.id === assetId);
    if (!asset) return;
    void safe(async () => {
      const scene = sim.currentScene();
      const position = dropPosition(
        hit || [
          0.08,
          (scene.objects.length % 4) * 0.07 - 0.1,
          scene.table.height,
        ],
        asset.dimensions,
        scene.table,
      );
      const id = `${asset.id}_${crypto.randomUUID().slice(0, 8)}`;
      scene.objects.push({
        id,
        name: asset.name,
        asset: asset.id,
        position,
        quaternion: [1, 0, 0, 0],
        scale: 1,
        mass: asset.mass,
        friction: [0.7, 0.005, 0.0001],
        collision: true,
        color: asset.color,
      });
      await sim.command("load", { scene });
      setSelected(id);
      notify(`${asset.name} placed`);
    });
  };
  const remove = () => {
    if (!selected) return;
    editScene((s) => {
      s.objects = s.objects.filter((o) => o.id !== selected);
    });
    setSelected(null);
  };
  const duplicate = () => {
    void safe(async () => {
      if (!editableRef.current) return;
      const scene = sim.currentScene(),
        obj = scene.objects.find((o) => o.id === selected);
      if (!obj) return;
      const copy = structuredClone(obj);
      copy.id = `${obj.asset}_${crypto.randomUUID().slice(0, 8)}`;
      copy.name += " copy";
      copy.position[1] += 0.09;
      scene.objects.push(copy);
      await sim.command("load", { scene });
      setSelected(copy.id);
    });
  };
  const saveCamera = (kind: ViewKind, value: Cameras["main"]) => {
    cameraRef.current = { ...cameraRef.current, [kind]: value };
    try {
      localStorage.setItem("so101.cameras", JSON.stringify(cameraRef.current));
    } catch {
      /* Camera remains available in memory. */
    }
  };
  const save = () => {
    if (!sim.snapshot) return;
    try {
      const doc = {
        version: 1,
        scene: sim.currentScene(),
        cameras: cameraRef.current,
      };
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `${doc.scene.name.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "scene"}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      notify("Scene and both camera views saved");
    } catch (e) {
      sim.setError(String(e));
    }
  };
  const load = async (file: File) => {
    await safe(async () => {
      if (file.size > 150000)
        throw Error("Scene file is too large (maximum 150 KB)");
      const doc = validateDocument(JSON.parse(await file.text()));
      await sim.command("load", { scene: doc.scene });
      if (doc.cameras) {
        cameraRef.current = doc.cameras;
        setCameras(doc.cameras);
        localStorage.setItem("so101.cameras", JSON.stringify(doc.cameras));
        setCameraEpoch((v) => v + 1);
      }
      setSelected(null);
      notify("Scene loaded");
    });
  };
  const runPause = () =>
    void safe(() => sim.command(sim.live.current?.running ? "pause" : "run"));
  const frame = () => setFrameSignal((x) => x + 1);
  const handlers = useRef({ save, remove, runPause, frame });
  handlers.current = { save, remove, runPause, frame };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        handlers.current.save();
        return;
      }
      if (
        (e.target as HTMLElement).closest(
          "input,textarea,select,[contenteditable]",
        )
      )
        return;
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        if (editableRef.current) handlers.current.remove();
      }
      if (e.key.toLowerCase() === "t") setTransform("translate");
      if (e.key.toLowerCase() === "r") setTransform("rotate");
      if (e.key.toLowerCase() === "f") handlers.current.frame();
      if (e.code === "Space") {
        e.preventDefault();
        handlers.current.runPause();
      }
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const snapShot = sim.snapshot;
  const scene = snapShot?.scene;
  // Paused inspection follows the latest authoritative pose after stepping.
  const displayScene = scene
    ? {
        ...scene,
        objects: scene.objects.map((o) => {
          const pose = sim.state?.objects.find((p) => p.id === o.id);
          return pose
            ? { ...o, position: pose.position, quaternion: pose.quaternion }
            : o;
        }),
      }
    : null;
  const common = snapShot
    ? {
        snapshot: snapShot,
        live: sim.live,
        meshes: sim.meshes,
        selected,
        select: setSelected,
        editable,
        transform,
        snap,
        onTransform: (id: string, position: Vec3, quaternion: Quat) =>
          patchObject(id, { position, quaternion }),
        onDrop: addObject,
        saveCamera,
        frameSignal,
        resetSignal,
        grid,
        cameraEpoch,
        preview,
      }
    : null;
  return (
    <div className="studio">
      <header className="app-header">
        <a className="brand" href="/" aria-label="Scene Studio home">
          <span className="brand-mark">
            <Bot size={23} />
          </span>
          <div>
            <strong>
              SCENE<span>STUDIO</span>
            </strong>
            <small>ROBOTICS WORKSPACE</small>
          </div>
        </a>
        <div className="project-title">
          <span className="project-divider" />
          <span className="project-icon">S</span>
          <div>
            <strong>{scene?.name || "Untitled workspace"}</strong>
            <small>SO-101 manipulation scene</small>
          </div>
          <span className="local-badge">LOCAL</span>
        </div>
        <div className="header-actions">
          <button
            className="icon-button"
            aria-label="Help and shortcuts"
            onClick={() => setHelp(true)}
          >
            <CircleHelp size={18} />
          </button>
          <button
            disabled={!editable}
            onClick={() => fileInput.current?.click()}
          >
            <ArrowUpFromLine size={15} />
            Open
          </button>
          <button
            className="save-button"
            disabled={!sim.snapshot}
            onClick={save}
          >
            <ArrowDownToLine size={15} />
            Save scene
          </button>
        </div>
        <input
          ref={fileInput}
          data-testid="scene-file"
          type="file"
          accept=".json,application/json"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void load(f);
            e.target.value = "";
          }}
        />
      </header>
      <div className="workspace-body">
        {scene && (
          <Library
            assets={sim.assets}
            scene={scene}
            selected={selected}
            select={setSelected}
            add={addObject}
            editable={editable}
          />
        )}
        <main className="main-panel">
          <div className="toolbar">
            <div className="tool-group">
              <button
                className={transform === "translate" ? "tool active" : "tool"}
                aria-label="Translate tool"
                title="Translate (T)"
                onClick={() => setTransform("translate")}
              >
                <Move size={16} />
                <span>Move</span>
              </button>
              <button
                className={transform === "rotate" ? "tool active" : "tool"}
                aria-label="Rotate tool"
                title="Rotate (R)"
                onClick={() => setTransform("rotate")}
              >
                <RotateCw size={16} />
                <span>Rotate</span>
              </button>
              <span className="tool-divider" />
              <button
                className={`tool ${snap ? "active" : ""}`}
                aria-label="Toggle snapping"
                title="Snap: 1 cm / 15°"
                onClick={() => setSnap((x) => !x)}
              >
                <Magnet size={16} />
              </button>
              <button
                className={`tool ${grid ? "active" : ""}`}
                aria-label="Toggle grid"
                onClick={() => setGrid((x) => !x)}
              >
                <Grid3X3 size={16} />
              </button>
              <button
                className="tool"
                title="Frame selected (F)"
                aria-label="Frame selected object"
                onClick={frame}
              >
                <Focus size={16} />
              </button>
            </div>
            <div className="tool-group">
              <button
                className={`tool ${dual ? "active" : ""}`}
                aria-label="Toggle dual viewport"
                onClick={() => {
                  setDual((v) => !v);
                  setSingleView("main");
                  setActive("main");
                }}
              >
                <Columns2 size={16} />
                <span>Dual view</span>
              </button>
              <span className="mode-badge">
                <span
                  className={sim.state?.running ? "running-dot" : "green-dot"}
                />
                {sim.state?.running ? "SIMULATING" : "EDIT MODE"}
              </span>
            </div>
          </div>
          <div className={`canvas-area ${dual ? "dual" : "single"}`}>
            <div className="workspace-heading">
              <div>
                <span className="eyebrow">WORKSPACE / 01</span>
                <h1>Build. Arrange. Simulate.</h1>
              </div>
              <div className="view-tabs">
                <button
                  className={dual || singleView === "main" ? "selected" : ""}
                  onClick={() => {
                    setSingleView("main");
                    setDual(false);
                    setActive("main");
                  }}
                >
                  Main 3D
                </button>
                <button
                  className={!dual && singleView === "top" ? "selected" : ""}
                  onClick={() => {
                    setSingleView("top");
                    setDual(false);
                    setActive("top");
                  }}
                >
                  Top view
                </button>
              </div>
            </div>
            {common && Object.keys(sim.meshes).length > 0 ? (
              <>
                <div className="primary-view">
                  <Viewport
                    {...common}
                    kind={dual ? "main" : singleView}
                    active={active === (dual ? "main" : singleView)}
                    onActive={() => setActive(dual ? "main" : singleView)}
                    cameraState={cameraRef.current[dual ? "main" : singleView]}
                  />
                </div>
                {dual && (
                  <div className="secondary-view">
                    <Viewport
                      {...common}
                      kind="top"
                      active={active === "top"}
                      onActive={() => setActive("top")}
                      cameraState={cameraRef.current.top}
                      onExpand={() => {
                        setDual(false);
                        setSingleView("top");
                        setActive("top");
                      }}
                    />
                  </div>
                )}
                {scene?.objects.length === 0 && (
                  <div className="empty-scene-hint">
                    <MousePointer2 size={17} />
                    <span>
                      Your scene starts here.
                      <small>
                        Drag an object from the library onto the table.
                      </small>
                    </span>
                    <ArrowUpRight size={17} />
                  </div>
                )}
                <div className="scene-label">
                  <span className="green-dot" />
                  SO-101
                  <span className="label-divider" />6 DOF
                  <span className="label-divider" />
                  FIXED BASE
                </div>
              </>
            ) : (
              <div className="loading">
                <LoaderCircle className="spin" size={28} />
                <strong>Preparing your workspace</strong>
                <span>Loading SO-101 geometry and MuJoCo…</span>
              </div>
            )}
          </div>
          <div className="simulation-bar">
            <div className="sim-label">
              <span className="physics-icon">μ</span>
              <div>
                <strong>MuJoCo Physics</strong>
                <small>
                  {sim.state?.running
                    ? "Simulation running"
                    : "Ready when you are"}
                </small>
              </div>
            </div>
            <div className="sim-controls">
              <button
                aria-label="Reset scene"
                title="Reset scene; preserve cameras"
                disabled={sim.busy || sim.status !== "connected"}
                onClick={() =>
                  void safe(async () => {
                    await sim.command("reset");
                    setSelected(null);
                    notify("Scene reset · camera views preserved");
                  })
                }
              >
                <RotateCcw size={16} />
              </button>
              <button
                className={sim.state?.running ? "pause-button" : "run-button"}
                disabled={sim.busy || sim.status !== "connected"}
                onClick={runPause}
              >
                {sim.state?.running ? (
                  <Pause size={15} />
                ) : (
                  <Play size={15} fill="currentColor" />
                )}
                {sim.state?.running ? "Pause" : "Run simulation"}
              </button>
              <button
                aria-label="Step simulation"
                title="Advance 20 ms"
                disabled={!editable}
                onClick={() => void safe(() => sim.command("step"))}
              >
                <SkipForward size={17} />
              </button>
            </div>
            <div className="sim-stats">
              <span>
                TIME
                <strong data-testid="simulation-time">
                  {(sim.state?.time || 0).toFixed(2)}
                  <small> s</small>
                </strong>
              </span>
              <span>
                CONTACTS<strong>{sim.state?.contacts || 0}</strong>
              </span>
            </div>
          </div>
        </main>
        {displayScene && snapShot && (
          <Inspector
            scene={displayScene}
            selected={selected}
            assets={sim.assets}
            joints={snapShot.jointInfo}
            editable={editable}
            patchObject={patchObject}
            editScene={editScene}
            remove={remove}
            duplicate={duplicate}
            frame={frame}
          />
        )}
      </div>
      <footer className="status-bar">
        <span>
          <i
            className={sim.status === "connected" ? "green-dot" : "offline-dot"}
          />
          {sim.status === "connected"
            ? "Simulation connected"
            : sim.status === "offline"
              ? "Reconnecting · scene retained"
              : "Connecting to simulation…"}
        </span>
        <span>
          {sim.busy ? (
            <>
              <LoaderCircle size={11} className="spin" />
              Updating scene…
            </>
          ) : (
            `${scene?.objects.length || 0} objects · ${sim.assets.length} assets`
          )}
          <span className="status-divider" />
          500 Hz physics · Z up · meters
        </span>
        <span>
          SO-101 Scene Studio<span className="version">v1.0</span>
        </span>
      </footer>
      {sim.error && (
        <div className="error-banner" role="alert">
          <strong>Update could not be applied</strong>
          <span>{sim.error}</span>
          <button aria-label="Dismiss error" onClick={() => sim.setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      )}
      {help && (
        <div className="modal-backdrop" onClick={() => setHelp(false)}>
          <div
            className="help-modal"
            role="dialog"
            aria-label="Help"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close"
              aria-label="Close help"
              onClick={() => setHelp(false)}
            >
              <X size={18} />
            </button>
            <span className="eyebrow">A LITTLE GUIDANCE</span>
            <h2>Your tabletop laboratory.</h2>
            <p>
              Drag an asset onto either viewport, or use its + button. Select an
              object to edit its pose and physical properties. Pause simulation
              before editing.
            </p>
            <div className="shortcut-list">
              {[
                ["T", "Move object"],
                ["R", "Rotate object"],
                ["F", "Frame selection"],
                ["Space", "Run / pause"],
                ["Delete", "Delete selection"],
                ["⌘ / Ctrl S", "Save scene"],
              ].map(([key, label]) => (
                <div key={key}>
                  <span>{label}</span>
                  <kbd>{key}</kbd>
                </div>
              ))}
            </div>
            <p className="quiet">
              Main view: drag to orbit, right-drag to pan, scroll to zoom. Top
              view: drag to pan, scroll to zoom. Cameras are independent. Scene
              reset clears objects and restores the robot; camera settings stay
              intact.
            </p>
            <p className="quiet">
              Cup, plate and spoon are procedural approximations. No autonomous
              manipulation controller is included.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
