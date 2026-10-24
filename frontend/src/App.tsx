import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { TaskPanel, type PickMode } from "./TaskPanel";
import { CameraEditor } from "./CameraEditor";
import { ImportDialog } from "./ImportDialog";
import { Library, type PlacementCursor } from "./Library";
import { Inspector } from "./Inspector";
import { rememberResetJoints } from "./robotPreferences";
import { Viewport } from "./Viewport";
import { useSimulation } from "./useSimulation";
import { nudgePosition, objectDimensions } from "./interaction";
import {
  dropPosition,
  readCameras,
  rememberCameraSetup,
  validateDocument,
} from "./math";
import type {
  Asset,
  TaskExample,
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
  const libraryAssets = useMemo(
    () =>
      sim.assets.filter((a) => a.id.startsWith("kalas_") || a.id === "cube"),
    [sim.assets],
  );
  const path = useMemo(
    () => sim.state?.plan?.points || [],
    [sim.state?.plan?.id],
  );
  const [dragAsset, setDragAsset] = useState<Asset | null>(null);
  const [dragCursor, setDragCursor] = useState<PlacementCursor | null>(null);
  const drag = useCallback((asset: Asset | null, cursor?: PlacementCursor) => {
    setDragAsset(asset);
    setDragCursor(cursor ?? null);
  }, []);
  useEffect(() => {
    if (dragCursor?.drop) {
      setDragAsset(null);
      setDragCursor(null);
    }
  }, [dragCursor]);
  const [highlight, setHighlight] = useState<{
    id: string;
    token: number;
  } | null>(null);
  const [examples, setExamples] = useState<TaskExample[]>([]);
  const [exampleId, setExampleId] = useState("kalas-cup-front");
  const nudges = useRef<{ id: string; key: string; fine: boolean }[]>([]);
  const nudging = useRef(false);
  useEffect(() => {
    const abort = new AbortController();
    fetch("/api/examples", { signal: abort.signal })
      .then((r) => r.json())
      .then(setExamples)
      .catch(() => {});
    return () => abort.abort();
  }, []);
  useEffect(() => {
    if (!highlight) return;
    const timer = setTimeout(() => setHighlight(null), 2600);
    return () => clearTimeout(timer);
  }, [highlight]);
  const [picking, setPicking] = useState<PickMode>(null);
  const [cameraEdit, setCameraEdit] = useState<ViewKind | null>(null);
  const [importing, setImporting] = useState(false);
  const [narrowPanel, setNarrowPanel] = useState<
    "library" | "inspector" | null
  >(null);
  const [apiHelp, setApiHelp] = useState(false);
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
      scene.cameras = {
        main: cameraRef.current.main,
        top: cameraRef.current.top,
        front: cameraRef.current.front,
        back: cameraRef.current.back,
      };
      await sim.command("load", { scene });
    });
  };
  const saveResetPose = (joints: number[], apply = false) => {
    if (!editableRef.current) return;
    void safe(async () => {
      await sim.command("robot", {
        patch: { reset_joints: joints, ...(apply ? { joints } : {}) },
      });
      try {
        rememberResetJoints(joints);
        notify("Reset position saved");
      } catch {
        notify(
          "Reset position saved in this scene. Browser storage is unavailable; save the scene file to keep it.",
        );
      }
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
      setNarrowPanel(null);
      notify(`${asset.name} placed`);
    });
  };
  const remove = () => {
    if (!selected) return;
    editScene((s) => {
      s.objects = s.objects.filter((o) => o.id !== selected);
      if (s.task.source === selected) s.task.source = null;
      if (s.task.target === selected) s.task.target = null;
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
  const selectObject = (id: string | null) => {
    setSelected(id);
    setHighlight(id ? { id, token: performance.now() } : null);
    if (
      !picking ||
      !id ||
      !editableRef.current ||
      !sim.snapshot?.scene.objects.some((o) => o.id === id)
    )
      return;
    const task = sim.snapshot.scene.task;
    if (
      (picking === "target" && task.source === id) ||
      (picking === "source" && task.target === id)
    ) {
      notify("Pick and destination must be different objects.");
      return;
    }
    const mode = picking;
    void safe(async () => {
      await sim.command("task", { ...task, [mode]: id });
      setNarrowPanel(null);
      setPicking(mode === "source" && !task.target ? "target" : null);
    });
  };
  const saveCamera = (
    kind: ViewKind,
    value: Cameras["main"],
    remember = false,
  ) => {
    if (kind === "wrist") return;
    if (remember) rememberCameraSetup(kind, value);
    const previous = cameraRef.current[kind];
    if (
      previous.position.every(
        (v, i) => Math.abs(v - value.position[i]) < 1e-6,
      ) &&
      previous.target.every((v, i) => Math.abs(v - value.target[i]) < 1e-6) &&
      Math.abs(previous.zoom - value.zoom) < 1e-6 &&
      Math.abs((previous.fov || 50) - (value.fov || 50)) < 1e-6
    )
      return;
    cameraRef.current = { ...cameraRef.current, [kind]: value };
    void safe(async () => {
      await sim.waitForPending();
      await sim.command("camera", { camera: kind, value });
    });
    try {
      localStorage.setItem("so101.cameras", JSON.stringify(cameraRef.current));
    } catch {
      /* Camera remains available in memory. */
    }
  };
  const save = async () => {
    if (!sim.snapshot) return;
    try {
      (document.activeElement as HTMLElement | null)?.blur();
      await sim.waitForPending();
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
      notify("Scene, task and camera views saved");
    } catch (e) {
      sim.setError(String(e));
    }
  };
  const load = async (file: File) => {
    await safe(async () => {
      if (file.size > 8_000_000)
        throw Error("Scene file is too large (maximum 8 MB)");
      const doc = validateDocument(JSON.parse(await file.text()));
      if (doc.cameras)
        doc.scene.cameras = {
          main: doc.cameras.main,
          top: doc.cameras.top,
          front: doc.cameras.front,
          back: doc.cameras.back,
        };
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
  const nudge = (key: string, fine: boolean) => {
    if (
      !selected ||
      sim.status !== "connected" ||
      sim.live.current?.running ||
      importing ||
      cameraEdit ||
      apiHelp ||
      help
    )
      return;
    if (!sim.snapshot?.scene.objects.some((o) => o.id === selected)) return;
    if (nudges.current.length < 128)
      nudges.current.push({ id: selected, key, fine });
    if (nudging.current) return;
    nudging.current = true;
    void safe(async () => {
      try {
        while (nudges.current.length) {
          await sim.waitForPending();
          if (sim.live.current?.running) {
            nudges.current = [];
            break;
          }
          const scene = sim.currentScene();
          const first = nudges.current.shift()!;
          const object = scene.objects.find((o) => o.id === first.id);
          if (!object) continue;
          const dimensions = objectDimensions(object, sim.assets);
          object.position = nudgePosition(
            object,
            dimensions,
            scene.table,
            first.key,
            first.fine,
          );
          while (nudges.current[0]?.id === object.id) {
            const next = nudges.current.shift()!;
            object.position = nudgePosition(
              object,
              dimensions,
              scene.table,
              next.key,
              next.fine,
            );
          }
          await sim.command("object_update", {
            id: object.id,
            patch: { position: object.position },
          });
        }
      } finally {
        nudging.current = false;
        nudges.current = [];
      }
    });
  };
  const chooseTask = (mode: PickMode) => {
    setPicking(mode);
    const id = mode ? sim.snapshot?.scene.task[mode] : null;
    if (id) {
      setSelected(id);
      setHighlight({ id, token: performance.now() });
    }
  };
  const runPause = () =>
    void safe(async () => {
      (document.activeElement as HTMLElement | null)?.blur();
      await sim.waitForPending();
      setPicking(null);
      const state = sim.live.current;
      if (state?.plan?.status === "calculating") return;
      await sim.command(
        state?.running
          ? "pause"
          : state?.task.status === "running" || state?.plan?.verified
            ? "run"
            : "plan",
      );
    });
  const frame = () => setFrameSignal((x) => x + 1);
  const handlers = useRef({ save, remove, runPause, frame, nudge });
  handlers.current = { save, remove, runPause, frame, nudge };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        handlers.current.save();
        return;
      }
      if (
        (e.target as HTMLElement).closest(
          "input,textarea,select,[contenteditable],[role=dialog]",
        )
      )
        return;
      if (e.key.startsWith("Arrow")) {
        e.preventDefault();
        handlers.current.nudge(e.key, e.shiftKey);
        return;
      }
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
      if (e.key === "Escape") {
        setSelected(null);
        setPicking(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    const incoming = sim.snapshot?.scene.cameras;
    if (!incoming) return;
    const next = { ...cameraRef.current, ...incoming };
    try {
      localStorage.setItem("so101.cameras", JSON.stringify(next));
    } catch {
      /* In-memory cameras remain usable. */
    }
    if (JSON.stringify(next) !== JSON.stringify(cameraRef.current)) {
      cameraRef.current = next;
      setCameras(next);
      setCameraEpoch((v) => v + 1);
    }
  }, [sim.snapshot?.scene.cameras]);
  const snapShot = sim.snapshot;
  const scene = snapShot?.scene;
  // Paused inspection follows the latest authoritative pose after stepping.
  const displayScene = scene
    ? {
        ...scene,
        robot: {
          ...scene.robot,
          joints: sim.state?.running ? sim.state.joints : scene.robot.joints,
        },
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
        assets: sim.assets,
        dragAsset,
        dragCursor,
        highlight,
        path,
        live: sim.live,
        meshes: sim.meshes,
        selected,
        select: selectObject,
        picking: !!picking,
        editCamera: setCameraEdit,
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
          <button onClick={() => setApiHelp(true)}>AI / API</button>
          <button
            className="icon-button"
            aria-label="Help and shortcuts"
            onClick={() => setHelp(true)}
          >
            <CircleHelp size={18} />
          </button>
          <button
            disabled={
              !editable && !(sim.status === "recovery-error" && !sim.busy)
            }
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
      <div className={`workspace-body narrow-${narrowPanel || "none"}`}>
        {scene && (
          <Library
            assets={libraryAssets}
            drag={drag}
            scene={scene}
            selected={selected}
            select={selectObject}
            onImport={() => {
              setImporting(true);
              setNarrowPanel(null);
            }}
            add={addObject}
            editable={editable}
          />
        )}
        <main className="main-panel">
          {scene && (
            <TaskPanel
              scene={scene}
              state={sim.state}
              editable={editable}
              picking={picking}
              setPicking={chooseTask}
              examples={examples}
              exampleId={exampleId}
              setExampleId={setExampleId}
              example={() =>
                void safe(async () => {
                  await sim.command("example", { exampleId });
                  setSelected(null);
                  setPicking(null);
                  notify("Example ready · calculate a path first");
                })
              }
              stop={() => void safe(() => sim.command("stop"))}
            />
          )}

          <div className="toolbar">
            <div className="narrow-tools">
              <button
                onClick={() =>
                  setNarrowPanel((v) => (v === "library" ? null : "library"))
                }
              >
                Objects
              </button>
              <button
                onClick={() =>
                  setNarrowPanel((v) =>
                    v === "inspector" ? null : "inspector",
                  )
                }
              >
                Inspector
              </button>
            </div>
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
                title="Frame selected in Main 3D (F)"
                disabled={active !== "main"}
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
                <span>Multi-view</span>
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
                <h1>See. Pick. Place.</h1>
              </div>
              <div className="view-tabs">
                {(["main", "top", "front", "back", "wrist"] as ViewKind[]).map(
                  (kind) => (
                    <button
                      key={kind}
                      className={
                        (dual ? kind === "main" : singleView === kind)
                          ? "selected"
                          : ""
                      }
                      onClick={() => {
                        setSingleView(kind);
                        setDual(false);
                        setActive(kind);
                      }}
                    >
                      {
                        {
                          main: "Main 3D",
                          top: "Top view",
                          front: "Front",
                          back: "Back",
                          wrist: "Wrist",
                        }[kind]
                      }
                    </button>
                  ),
                )}
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
                  <div className="observation-strip">
                    {(["top", "front", "back", "wrist"] as ViewKind[]).map(
                      (kind) => (
                        <div
                          className={`observation-view observation-${kind}`}
                          key={kind}
                        >
                          <Viewport
                            {...common}
                            kind={kind}
                            active={active === kind}
                            onActive={() => setActive(kind)}
                            cameraState={cameraRef.current[kind]}
                            onExpand={() => {
                              setDual(false);
                              setSingleView(kind);
                              setActive(kind);
                            }}
                          />
                        </div>
                      ),
                    )}
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
                  <span className="label-divider" />5 AXES + GRIPPER
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
            <div className="sim-controls">
              <button
                title="Run passive physics without the robot policy"
                disabled={!editable}
                onClick={() => void safe(() => sim.command("physics"))}
              >
                Physics only
              </button>
              <button
                aria-label="Reset scene"
                title="Reset scene to saved robot pose; preserve cameras"
                disabled={
                  sim.busy ||
                  !["connected", "recovery-error"].includes(sim.status)
                }
                onClick={() =>
                  void safe(async () => {
                    await sim.command("reset");
                    setSelected(null);
                    notify("Scene reset · saved robot pose applied");
                  })
                }
              >
                <RotateCcw size={16} />
              </button>
              <button
                className={sim.state?.running ? "pause-button" : "run-button"}
                disabled={
                  sim.busy ||
                  sim.status !== "connected" ||
                  sim.state?.plan?.status === "calculating"
                }
                onClick={runPause}
              >
                {sim.state?.running ? (
                  <Pause size={15} />
                ) : (
                  <Play size={15} fill="currentColor" />
                )}
                {sim.state?.running
                  ? "Pause"
                  : sim.state?.plan?.status === "calculating"
                    ? "Calculating…"
                    : sim.state?.task.status === "running" ||
                        sim.state?.plan?.verified
                      ? "Run simulation"
                      : "Calculate path"}
              </button>
              <button
                aria-label="Step simulation"
                title="Advance 20 ms"
                disabled={!editable}
                onClick={() =>
                  void safe(() =>
                    sim.command("step", {
                      count: Math.round(0.02 / (sim.state?.timeStep || 0.002)),
                    }),
                  )
                }
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
            saveResetPose={saveResetPose}
            remove={remove}
            duplicate={duplicate}
            frame={frame}
            select={selectObject}
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
            : sim.status === "recovery-error"
              ? "Restore needs attention · scene retained"
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
            `${scene?.objects.length || 0} objects · ${libraryAssets.length} assets`
          )}
          <span className="status-divider" />
          {Math.round(1 / (sim.state?.timeStep || 0.002))} Hz physics · Z up ·
          meters
        </span>
        <span>
          <button
            data-testid="session-id"
            data-session-id={sim.state?.sessionId}
            onClick={() => setApiHelp(true)}
            title="Connect an AI agent to this scene"
          >
            Session {sim.state?.sessionId?.slice(0, 8) || "…"}
          </button>
          <span className="version">v3.2</span>
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
      {cameraEdit && (
        <CameraEditor
          kind={cameraEdit}
          value={cameraRef.current[cameraEdit]}
          close={() => setCameraEdit(null)}
          apply={async (value) => {
            await sim.waitForPending();
            await sim.command("camera", { camera: cameraEdit, value });
            if (cameraEdit !== "wrist") rememberCameraSetup(cameraEdit, value);
            cameraRef.current = { ...cameraRef.current, [cameraEdit]: value };
            setCameras(cameraRef.current);
            setCameraEpoch((v) => v + 1);
          }}
        />
      )}
      {importing && (
        <ImportDialog
          close={() => setImporting(false)}
          add={async (obj) => {
            await sim.waitForPending();
            const scene = sim.currentScene();
            const zValues = obj.mesh!.vertices.filter((_, i) => i % 3 === 2);
            obj.position = [
              0.06,
              0,
              scene.table.height + Math.max(...zValues) + 0.002,
            ];
            await sim.command("object_add", { object: obj });
            setSelected(obj.id);
            notify("Object imported · convex hull collision");
          }}
        />
      )}
      {apiHelp && (
        <div className="modal-backdrop">
          <div
            className="workbench-modal"
            role="dialog"
            aria-label="AI and API connection"
          >
            <button
              className="close"
              onClick={() => setApiHelp(false)}
              aria-label="Close API help"
            >
              <X size={18} />
            </button>
            <span className="eyebrow">CONNECT YOUR AGENT</span>
            <h2>One scene. Any controller.</h2>
            <p>Use this session ID to control exactly what you see here.</p>
            <code className="session-code">{sim.state?.sessionId}</code>
            <button
              className="primary-action"
              onClick={() => {
                void navigator.clipboard
                  .writeText(sim.state?.sessionId || "")
                  .then(() => notify("Session ID copied"));
              }}
            >
              Copy session ID
            </button>
            <h3>MCP</h3>
            <p>Start the official SDK bridge from the project folder:</p>
            <pre>bash scripts/mcp.sh</pre>
            <h3>HTTP API</h3>
            <p>
              <a
                href="http://127.0.0.1:8765/docs"
                target="_blank"
                rel="noreferrer"
              >
                Open interactive API documentation ↗
              </a>
            </p>
            <pre>{`POST /api/sessions/${sim.state?.sessionId}/command\n{ "type": "example" }\n{ "type": "run" }`}</pre>
            <p className="quiet">
              Read status to check success. The API and MCP can edit objects,
              cameras, robot joints, task instructions and complete scenes. See
              docs/API.md for client configuration.
            </p>
          </div>
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
                ["F", "Frame selection in Main 3D"],
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
              view: scroll to zoom, robot side below. Front and Back stay at
              their saved setup. Scene reset clears objects and restores the
              robot; camera settings stay intact.
            </p>
            <p className="quiet">
              The IK policy uses physical jaw contact and friction. A lost grasp
              lets the object fall and fails the task. Success is measured after
              release. Load the spoon → cup example to try it. Imported meshes
              use solid convex collision.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
