import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Camera,
  Check,
  Database,
  Download,
  LoaderCircle,
  Palette,
  Play,
  Square,
} from "lucide-react";
import { DatasetViewer } from "./DatasetViewer";
import type { Scene, Pattern } from "./types";
import {
  paletteRules,
  patternRules,
  terminalStatuses,
} from "./collectionTypes";
import type {
  CollectionConfig,
  CollectionScene,
  CollectionJob,
  PaletteKey,
  PatternKey,
} from "./collectionTypes";

const colorOptions = [
  ["Orange", "#f1792e"],
  ["Yellow", "#ffd11f"],
  ["White", "#ffffff"],
  ["Gray", "#808080"],
  ["Black", "#202020"],
  ["Blue", "#668ad5"],
  ["Green", "#6f9b77"],
  ["Pink", "#e78dbe"],
  ["Red", "#d95454"],
];
const patterns: Pattern[] = [
  "solid",
  "checker",
  "stripes",
  "dots",
  "wood",
  "terrazzo",
  "tiles",
  "noise",
];
const layouts = ["open", "studio", "room", "warehouse", "panels"];

async function responseJSON(response: Response) {
  const value = await response.json();
  if (!response.ok)
    throw Error(
      typeof value.detail === "string"
        ? value.detail
        : "Check the collection settings and try again.",
    );
  return value;
}
function PaletteRule({
  name,
  value,
  enabled,
  toggle,
  update,
}: {
  name: string;
  value: string[];
  enabled: boolean;
  toggle: () => void;
  update: (colors: string[]) => void;
}) {
  const [custom, setCustom] = useState("#7799bb");
  const choices = [...new Set([...colorOptions.map((c) => c[1]), ...value])];
  return (
    <section className={`collect-rule ${enabled ? "enabled" : ""}`}>
      <div className="collect-rule-heading">
        <label className="look-check">
          <input
            aria-label={`Randomize ${name.toLowerCase()} color`}
            type="checkbox"
            checked={enabled}
            onChange={toggle}
          />
          <strong>{name} color</strong>
          <span>{enabled ? `${value.length} choices` : "Keep current"}</span>
        </label>
        <button
          type="button"
          className="collect-all"
          aria-label={`Select all ${name.toLowerCase()} colors`}
          aria-pressed={
            enabled && choices.every((color) => value.includes(color))
          }
          onClick={() => {
            if (!enabled) toggle();
            update(choices);
          }}
        >
          All
        </button>
      </div>
      {enabled && (
        <>
          <div className="collect-swatches">
            {choices.map((color) => (
              <button
                key={color}
                type="button"
                title={colorOptions.find((c) => c[1] === color)?.[0] || color}
                aria-label={`${name} ${colorOptions.find((c) => c[1] === color)?.[0] || color}`}
                aria-pressed={value.includes(color)}
                style={{ background: color }}
                onClick={() =>
                  update(
                    value.includes(color)
                      ? value.filter((v) => v !== color)
                      : [...value, color],
                  )
                }
              >
                {value.includes(color) && <Check size={14} />}
              </button>
            ))}
          </div>
          <div className="collect-custom">
            <input
              aria-label={`${name} custom color`}
              type="color"
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
            />
            <code>{custom}</code>
            <button
              type="button"
              disabled={value.includes(custom) || choices.length >= 32}
              onClick={() => update([...value, custom])}
            >
              Add color
            </button>
          </div>
          {value.length === 0 && (
            <p className="look-error">Choose at least one color.</p>
          )}
        </>
      )}
    </section>
  );
}
interface Props {
  topReferenceHeight: number;
  scene: Scene;
  sessionId: string;
  editable: boolean;
  close: () => void;
}
export function CollectionPanel({
  scene,
  sessionId,
  editable,
  close,
  topReferenceHeight,
}: Props) {
  const [config, setConfig] = useState<CollectionConfig | null>(null);
  const [scenes, setScenes] = useState<CollectionScene[]>([]);
  const [sceneFilter, setSceneFilter] = useState("");
  const [ready, setReady] = useState(false);
  const [jobs, setJobs] = useState<CollectionJob[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("capture");
  const [viewing, setViewing] = useState<string | null>(null);
  const pageRef = useRef<HTMLElement>(null);
  const lastViewed = useRef<string | null>(null);
  const [enabledColors, setEnabledColors] = useState<Set<PaletteKey>>(
    new Set(),
  );
  const [enabledPatterns, setEnabledPatterns] = useState<Set<PatternKey>>(
    new Set(),
  );
  const [varyLayout, setVaryLayout] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);
  const scrollPanel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollPanel.current?.scrollTo({ top: 0 });
  }, [tab]);
  useEffect(() => {
    if (viewing) {
      pageRef.current
        ?.querySelector<HTMLButtonElement>("[data-dataset-back]")
        ?.focus();
    } else if (lastViewed.current) {
      pageRef.current
        ?.querySelector<HTMLButtonElement>(
          `[data-testid="collection-job-${CSS.escape(lastViewed.current)}"] .collect-visualize`,
        )
        ?.focus();
    }
  }, [viewing]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const background = Array.from(
      pageRef.current?.parentElement?.children || [],
    ).filter(
      (element): element is HTMLElement =>
        element instanceof HTMLElement && element !== pageRef.current,
    );
    const prior = background.map((element) => element.inert);
    background.forEach((element) => {
      element.inert = true;
    });
    closeButton.current?.focus();
    return () => {
      background.forEach((element, i) => {
        element.inert = prior[i];
      });
      previous?.focus();
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/collection", { signal: controller.signal })
      .then(responseJSON)
      .then((data) => {
        const defaults = data.defaults as CollectionConfig;
        defaults.top_reference_height = topReferenceHeight;
        defaults.cameras ??= ["main", "top", "front", "back", "wrist"];
        defaults.variation.position_mode ??= "workspace";
        defaults.duration_mode ??= "auto";
        setReady(data.ready);
        setScenes(data.scenes);
        setEnabledPatterns(
          new Set(
            patternRules
              .filter((r) => defaults.variation[r.key].length)
              .map((r) => r.key),
          ),
        );
        setVaryLayout(defaults.variation.environments.length > 0);
        setEnabledColors(
          new Set(
            paletteRules
              .filter((r) => defaults.variation[r.key].length)
              .map((r) => r.key),
          ),
        );
        paletteRules.forEach((r) => {
          if (!defaults.variation[r.key].length)
            defaults.variation[r.key] = [...r.defaults];
        });
        patternRules.forEach((r) => {
          if (!defaults.variation[r.key].length)
            defaults.variation[r.key] = [...patterns];
        });
        if (!defaults.variation.environments.length)
          defaults.variation.environments = [...layouts];
        const source = scene.objects.find((o) => o.id === scene.task.source);
        const target = scene.objects.find((o) => o.id === scene.task.target);
        if (source && target)
          defaults.task = `Pick up ${source.name} and place it in or on ${target.name}.`;
        if (!source || !target) {
          const first = data.scenes[0] as CollectionScene;
          defaults.scene_id = first.id;
          defaults.name = `${first.id}-demonstrations`;
          defaults.task = first.instruction;
        }
        setConfig(defaults);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e));
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const refresh = () =>
      fetch("/api/collection/jobs", { signal: controller.signal })
        .then(responseJSON)
        .then((data) => {
          if (active) setJobs(data);
        })
        .catch((e) => {
          if (active && !controller.signal.aborted) setError(String(e));
        });
    void refresh();
    const timer = setInterval(() => void refresh(), 1500);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, []);
  const patch = (value: Partial<CollectionConfig>) =>
    setConfig((c) => (c ? { ...c, ...value } : c));
  const variation = (key: string, value: unknown) =>
    setConfig((c) =>
      c ? { ...c, variation: { ...c.variation, [key]: value } } : c,
    );
  const activeJob = jobs.find((j) => !terminalStatuses.includes(j.status));
  const selectedTask =
    !!config?.scene_id || (!!scene.task.source && !!scene.task.target);
  const selectScene = (id: string) => {
    const selected = scenes.find((s) => s.id === id);
    const source = scene.objects.find((o) => o.id === scene.task.source);
    const target = scene.objects.find((o) => o.id === scene.task.target);
    patch({
      scene_id: id || null,
      name: `${id || "current-scene"}-demonstrations`,
      task:
        selected?.instruction ||
        (source && target
          ? `Pick up ${source.name} and place it in or on ${target.name}.`
          : "Pick up the source object and place it in the destination."),
    });
  };
  const visibleJobs = jobs.filter(
    (job) =>
      !sceneFilter || (job.scene_name || "Earlier datasets") === sceneFilter,
  );
  const attemptMultiplier =
    config?.variation.positions &&
    config.variation.position_mode === "workspace"
      ? 50
      : 5;
  const valid =
    !!config &&
    config.cameras.length > 0 &&
    /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(config.name) &&
    !!config.task.trim() &&
    Number.isInteger(config.episodes) &&
    config.episodes >= 1 &&
    config.episodes <= 100 &&
    Number.isInteger(config.seed) &&
    config.seed >= 0 &&
    config.seed + config.episodes * attemptMultiplier - 1 <= 2147483647 &&
    Number.isInteger(config.max_seconds) &&
    config.max_seconds >= 1 &&
    config.max_seconds <= 120 &&
    paletteRules.every(
      (r) => !enabledColors.has(r.key) || config.variation[r.key].length > 0,
    ) &&
    patternRules.every(
      (r) => !enabledPatterns.has(r.key) || config.variation[r.key].length > 0,
    ) &&
    (!varyLayout || config.variation.environments.length > 0) &&
    config.variation.repeat_min <= config.variation.repeat_max &&
    config.variation.position_radius >= 0.01 &&
    config.variation.position_radius <= 0.4;
  const start = async () => {
    if (!config) return;
    setBusy(true);
    setError("");
    const value = structuredClone(config);
    paletteRules.forEach((r) => {
      if (!enabledColors.has(r.key)) value.variation[r.key] = [];
    });
    patternRules.forEach((r) => {
      if (!enabledPatterns.has(r.key)) value.variation[r.key] = [];
    });
    if (!varyLayout) value.variation.environments = [];
    try {
      const job = await responseJSON(
        await fetch(`/api/sessions/${sessionId}/collection`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(value),
        }),
      );
      setJobs((old) => [job, ...old.filter((j) => j.id !== job.id)]);
      setTab("jobs");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const cancel = async (job: CollectionJob) => {
    setBusy(true);
    setError("");
    try {
      const result = await responseJSON(
        await fetch(`/api/collection/jobs/${job.id}/cancel`, {
          method: "POST",
        }),
      );
      setJobs((old) => old.map((j) => (j.id === result.id ? result : j)));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <aside
      ref={pageRef}
      className="appearance-studio collection-panel"
      data-testid="collection-page"
      data-tab={tab}
      aria-modal="true"
      role="dialog"
      aria-label="Data collection"
      onKeyDown={(e) => {
        if (e.key === "Tab") {
          const focusable = Array.from(
            e.currentTarget.querySelectorAll<HTMLElement>(
              'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
            ),
          ).filter((el) => el.offsetParent !== null);
          if (e.shiftKey && document.activeElement === focusable[0]) {
            e.preventDefault();
            focusable.at(-1)?.focus();
          } else if (
            !e.shiftKey &&
            document.activeElement === focusable.at(-1)
          ) {
            e.preventDefault();
            focusable[0]?.focus();
          }
        }
        if (e.key === "Escape") {
          e.stopPropagation();
          close();
        }
      }}
    >
      <header className="look-header">
        <div className="look-icon">
          <Database size={22} />
        </div>
        <div>
          <small>LEROBOT V3 · LOCAL DATASETS</small>
          <h2>Collect demonstrations</h2>
        </div>
        <button
          ref={closeButton}
          onClick={close}
          aria-label="Close data collection"
        >
          <ArrowLeft size={17} />
          <span>Back to editor</span>
        </button>
      </header>
      <div className="look-intro">
        One scene. Many demonstrations.
        <span>Selected camera views · measured joints · full trajectory</span>
      </div>
      <nav
        className="look-tabs collect-tabs"
        aria-label="Collection categories"
      >
        {[
          { id: "capture", name: "Capture", Icon: Camera },
          { id: "randomization", name: "Randomization", Icon: Palette },
          { id: "jobs", name: "Datasets", Icon: Database },
        ].map(({ id, name, Icon }) => (
          <button
            key={id}
            aria-pressed={tab === id}
            onClick={() => {
              setTab(id);
              setViewing(null);
            }}
          >
            <Icon size={15} />
            {name}
            {id === "jobs" && activeJob && <i className="green-dot" />}
          </button>
        ))}
      </nav>
      <div className="look-scroll" ref={scrollPanel}>
        {!config && (
          <p className="collect-note">Loading collection settings…</p>
        )}
        {config && tab === "capture" && (
          <div className="collect-capture-grid">
            <section className="look-section">
              <h3>
                Dataset<span>ON THIS COMPUTER</span>
              </h3>
              <label className="collect-input">
                Scene
                <select
                  aria-label="Dataset scene"
                  value={config.scene_id || ""}
                  onChange={(e) => selectScene(e.target.value)}
                >
                  <option value="">Current editor scene · {scene.name}</option>
                  {scenes.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <p>
                One scene per dataset. Choose another scene to generate a
                separate dataset.
              </p>
              <label className="collect-input">
                Dataset name
                <input
                  aria-label="Dataset name"
                  value={config.name}
                  maxLength={64}
                  onChange={(e) => patch({ name: e.target.value })}
                />
              </label>
              <label className="collect-input">
                Task instruction
                <textarea
                  aria-label="Task instruction"
                  value={config.task}
                  maxLength={500}
                  rows={3}
                  onChange={(e) => patch({ task: e.target.value })}
                />
              </label>
              <div className="collect-grid">
                <label className="collect-input">
                  Episodes to generate
                  <input
                    aria-label="Episodes"
                    type="number"
                    min={1}
                    max={100}
                    value={config.episodes}
                    onChange={(e) =>
                      patch({ episodes: Number(e.target.value) })
                    }
                  />
                </label>
                <label className="collect-input">
                  Starting seed
                  <input
                    aria-label="Starting seed"
                    type="number"
                    min={0}
                    max={2147483647}
                    value={config.seed}
                    onChange={(e) => patch({ seed: Number(e.target.value) })}
                  />
                </label>
              </div>
              <p>
                Generate {config.episodes} retained episodes, starting at seed{" "}
                {config.seed}. Rejected placements use a new seed. Up to{" "}
                {config.episodes * attemptMultiplier} attempts; progress counts
                saved episodes.
              </p>
            </section>
            <section className="look-section">
              <h3>Object positions</h3>
              <label className="look-check">
                <input
                  type="checkbox"
                  checked={config.variation.positions}
                  onChange={(e) => variation("positions", e.target.checked)}
                />
                Randomize object positions
              </label>
              {config.variation.positions && (
                <label className="look-select">
                  Position sampling
                  <select
                    aria-label="Position sampling"
                    value={config.variation.position_mode}
                    onChange={(e) => variation("position_mode", e.target.value)}
                  >
                    <option value="workspace">
                      Reachable workspace · wide variation
                    </option>
                    <option value="radius">Around original positions</option>
                  </select>
                </label>
              )}
              {config.variation.positions &&
                config.variation.position_mode === "radius" && (
                  <label className="collect-input">
                    Position radius (cm)
                    <input
                      aria-label="Position radius (cm)"
                      type="number"
                      min={1}
                      max={40}
                      step={0.5}
                      value={
                        Math.round(config.variation.position_radius * 1000) / 10
                      }
                      onChange={(e) =>
                        variation(
                          "position_radius",
                          Number(e.target.value) / 100,
                        )
                      }
                    />
                  </label>
                )}
              <p>
                {config.variation.position_mode === "workspace"
                  ? "Search broadly across the table near the arm. Only placements that complete a physical pick-and-place rehearsal proceed to capture."
                  : "Move pick and destination objects independently within the radius of their original positions. Every new placement is rehearsed before capture."}{" "}
                Objects inside a cup move with it. Positions stay on the table.
              </p>
            </section>
            <section className="look-section">
              <h3>
                Capture settings<span>SIMULATION TIME</span>
              </h3>
              <div className="collect-cameras">
                {["main", "top", "front", "back", "wrist"].map((v) => (
                  <label
                    key={v}
                    className={config.cameras.includes(v) ? "selected" : ""}
                  >
                    <input
                      type="checkbox"
                      aria-label={`Capture ${v} view`}
                      checked={config.cameras.includes(v)}
                      onChange={() =>
                        patch({
                          cameras: config.cameras.includes(v)
                            ? config.cameras.filter((camera) => camera !== v)
                            : [...config.cameras, v],
                        })
                      }
                    />
                    <Camera size={14} />
                    {v}
                  </label>
                ))}
              </div>
              <button
                className="collect-all"
                type="button"
                onClick={() =>
                  patch({ cameras: ["main", "top", "front", "back", "wrist"] })
                }
              >
                Select all views
              </button>
              {config.cameras.length === 0 && (
                <p className="look-error" role="alert">
                  Select at least one camera view.
                </p>
              )}
              <p>
                {config.cameras.length} selected views are recorded at the same
                simulation time.
              </p>
              <label className="look-select">
                Frame rate
                <select
                  aria-label="Frame rate"
                  value={config.fps}
                  onChange={(e) => patch({ fps: Number(e.target.value) })}
                >
                  {[10, 20, 25, 50].map((v) => (
                    <option key={v} value={v}>
                      {v} FPS
                    </option>
                  ))}
                </select>
              </label>
              <label className="look-select">
                Image resolution
                <select
                  aria-label="Image resolution"
                  value={config.resolution}
                  onChange={(e) => patch({ resolution: e.target.value })}
                >
                  <option value="640x480">640 × 480</option>
                  <option value="320x240">320 × 240</option>
                </select>
              </label>
              <label className="look-select">
                Episode duration
                <select
                  aria-label="Episode duration"
                  value={config.duration_mode}
                  onChange={(e) =>
                    patch({ duration_mode: e.target.value as "auto" | "fixed" })
                  }
                >
                  <option value="auto">Automatic · finish the task</option>
                  <option value="fixed">Fixed time limit</option>
                </select>
              </label>
              {config.duration_mode === "fixed" && (
                <label className="look-select">
                  Episode time limit
                  <input
                    aria-label="Episode time limit"
                    type="number"
                    min={1}
                    max={120}
                    value={config.max_seconds}
                    onChange={(e) =>
                      patch({ max_seconds: Number(e.target.value) })
                    }
                  />
                </label>
              )}
              <p>
                {config.duration_mode === "auto"
                  ? "Time allowance follows the successful rehearsal with extra margin. Recording stops when the task finishes."
                  : "Seconds of simulation. A limit shorter than the rehearsal is rejected unless failed episodes are enabled."}
              </p>
              <label className="look-check">
                <input
                  type="checkbox"
                  checked={config.include_failed}
                  onChange={(e) => patch({ include_failed: e.target.checked })}
                />
                Include failed episodes
              </label>
              {config.include_failed && (
                <p className="look-error" role="alert">
                  Failed and timed-out attempts will be saved too. They are not
                  successful demonstrations.
                </p>
              )}
              <p>
                Successful tasks finish automatically. Failed or timed-out
                attempts are excluded unless enabled above. Stopping a job
                discards its unfinished episode.
              </p>
            </section>
            <section className="look-section">
              <h3>What is recorded</h3>
              <ul className="collect-features">
                <li>RGB video from your selected native MuJoCo cameras</li>
                <li>
                  Joint positions, velocities, actuator forces and command
                  targets
                </li>
                <li>Tool position and orientation, plus 1,000 Hz trajectory</li>
                <li>
                  Task instruction, seed, scene recipe and episode outcome
                </li>
              </ul>
              <p>
                Capture advances with simulation time, so slow rendering does
                not drop frames. The editor scene stays available while an
                independent copy records.
              </p>
            </section>
          </div>
        )}
        {config && tab === "randomization" && (
          <div className="collect-random-grid">
            <section className="look-section">
              <h3>
                Color palettes<span>ALLOWED PER EPISODE</span>
              </h3>
              <p>
                Enable a category and select its allowed colors. Unchecked
                categories keep the captured scene's values. Surface palettes
                also constrain the secondary color of existing patterns.
              </p>
              <div className="collect-palette-grid">
                {paletteRules.map((rule) => (
                  <PaletteRule
                    key={rule.key}
                    name={rule.name}
                    value={config.variation[rule.key]}
                    enabled={enabledColors.has(rule.key)}
                    toggle={() =>
                      setEnabledColors((old) => {
                        const next = new Set(old);
                        if (next.has(rule.key)) next.delete(rule.key);
                        else next.add(rule.key);
                        return next;
                      })
                    }
                    update={(colors) => variation(rule.key, colors)}
                  />
                ))}
              </div>
            </section>
            <section className="look-section">
              <h3>Patterns & finishes</h3>
              {patternRules.map((rule) => (
                <div className="collect-rule" key={rule.key}>
                  <div className="collect-rule-heading">
                    <label className="look-check">
                      <input
                        aria-label={`Randomize ${rule.name.toLowerCase()} pattern`}
                        type="checkbox"
                        checked={enabledPatterns.has(rule.key)}
                        onChange={() =>
                          setEnabledPatterns((old) => {
                            const next = new Set(old);
                            if (next.has(rule.key)) next.delete(rule.key);
                            else next.add(rule.key);
                            return next;
                          })
                        }
                      />
                      {rule.name} pattern
                    </label>
                    <button
                      type="button"
                      className="collect-all"
                      aria-label={`Select all ${rule.name.toLowerCase()} patterns`}
                      aria-pressed={
                        enabledPatterns.has(rule.key) &&
                        patterns.every((p) =>
                          config.variation[rule.key].includes(p),
                        )
                      }
                      onClick={() => {
                        setEnabledPatterns(
                          (old) => new Set([...old, rule.key]),
                        );
                        variation(rule.key, [...patterns]);
                      }}
                    >
                      All
                    </button>
                  </div>
                  {enabledPatterns.has(rule.key) && (
                    <div className="collect-chips">
                      {patterns.map((p) => (
                        <button
                          key={p}
                          aria-pressed={config.variation[rule.key].includes(p)}
                          onClick={() =>
                            variation(
                              rule.key,
                              config.variation[rule.key].includes(p)
                                ? config.variation[rule.key].filter(
                                    (v) => v !== p,
                                  )
                                : [...config.variation[rule.key], p],
                            )
                          }
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <div className="collect-grid">
                <label className="collect-input">
                  Repeat minimum
                  <input
                    aria-label="Pattern repeat minimum"
                    type="number"
                    min={1}
                    max={24}
                    value={config.variation.repeat_min}
                    onChange={(e) =>
                      variation("repeat_min", Number(e.target.value))
                    }
                  />
                </label>
                <label className="collect-input">
                  Repeat maximum
                  <input
                    aria-label="Pattern repeat maximum"
                    type="number"
                    min={1}
                    max={24}
                    value={config.variation.repeat_max}
                    onChange={(e) =>
                      variation("repeat_max", Number(e.target.value))
                    }
                  />
                </label>
              </div>
              <label className="look-check">
                <input
                  type="checkbox"
                  checked={config.variation.finishes}
                  onChange={(e) => variation("finishes", e.target.checked)}
                />
                Randomize material finishes
              </label>
            </section>
            <section className="look-section">
              <h3>Environment & lighting</h3>
              <label className="look-check">
                <input
                  type="checkbox"
                  checked={varyLayout}
                  onChange={(e) => setVaryLayout(e.target.checked)}
                />
                Randomize environment layout
              </label>
              <button
                type="button"
                className="collect-all"
                aria-label="Select all environment layouts"
                aria-pressed={
                  varyLayout &&
                  layouts.every((v) =>
                    config.variation.environments.includes(v),
                  )
                }
                onClick={() => {
                  setVaryLayout(true);
                  variation("environments", [...layouts]);
                }}
              >
                All
              </button>
              {varyLayout && (
                <div className="collect-chips">
                  {layouts.map((v) => (
                    <button
                      key={v}
                      aria-pressed={config.variation.environments.includes(v)}
                      onClick={() =>
                        variation(
                          "environments",
                          config.variation.environments.includes(v)
                            ? config.variation.environments.filter(
                                (x) => x !== v,
                              )
                            : [...config.variation.environments, v],
                        )
                      }
                    >
                      {v}
                    </button>
                  ))}
                </div>
              )}
              <label className="look-check">
                <input
                  type="checkbox"
                  checked={config.variation.lighting}
                  onChange={(e) => variation("lighting", e.target.checked)}
                />
                Randomize lighting
              </label>
              <p>
                Appearance choices preserve camera setup, mass and friction.
                Object placement is controlled separately in Capture.
              </p>
            </section>
          </div>
        )}
        {tab === "jobs" && viewing && (
          <DatasetViewer
            key={viewing}
            jobId={viewing}
            back={() => setViewing(null)}
          />
        )}
        {tab === "jobs" && !viewing && (
          <section className="look-section">
            <h3>
              Collection jobs<span>{jobs.length} LOCAL</span>
            </h3>
            <label className="collect-input">
              Scene
              <select
                aria-label="Filter datasets by scene"
                value={sceneFilter}
                onChange={(e) => setSceneFilter(e.target.value)}
              >
                <option value="">All scenes</option>
                {[
                  ...new Set(
                    jobs.map((job) => job.scene_name || "Earlier datasets"),
                  ),
                ].map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            {visibleJobs.length === 0 && (
              <p>No datasets yet. Configure a capture and start collection.</p>
            )}
            <div className="collect-jobs-grid">
              {visibleJobs.map((job) => (
                <article
                  className="collect-job"
                  key={job.id}
                  data-testid={`collection-job-${job.id}`}
                >
                  <div className="collect-job-title">
                    <strong>{job.name}</strong>
                    <span className={`collect-status ${job.status}`}>
                      {job.status}
                    </span>
                  </div>
                  <p className="collect-scene-name">
                    {job.scene_name || "Earlier dataset"}
                  </p>
                  {(job.frames > 0 || job.saved_episodes > 0) && (
                    <img
                      className="collect-preview"
                      src={`/api/collection/jobs/${job.id}/preview?t=${job.updated_at}`}
                      alt={`Latest recorded camera frame for ${job.name}`}
                    />
                  )}
                  <div className="collect-metrics">
                    <span>
                      Target{" "}
                      <b>
                        {job.saved_episodes}/{job.episodes}
                      </b>
                    </span>
                    <span>
                      Attempt{" "}
                      <b>
                        {job.attempt ?? job.episode}/
                        {job.max_attempts ?? job.episodes}
                      </b>
                    </span>
                    <span>
                      Seed <b>{job.seed}</b>
                    </span>
                    <span>
                      Frames <b>{job.total_frames}</b>
                    </span>
                  </div>
                  <progress max={job.episodes} value={job.saved_episodes} />
                  {job.successful_episodes !== undefined && (
                    <p className="collect-outcomes">
                      {job.successful_episodes} successful ·{" "}
                      {job.unsuccessful_episodes ?? 0} unsuccessful
                    </p>
                  )}
                  {job.download_available &&
                    job.saved_episodes > 0 &&
                    job.successful_episodes === 0 && (
                      <p className="look-error">
                        No successful demonstrations in this dataset.
                      </p>
                    )}
                  <p role="status">
                    {job.cancel_requested &&
                    !terminalStatuses.includes(job.status)
                      ? "Stopping after the current operation…"
                      : job.message}
                  </p>
                  {!terminalStatuses.includes(job.status) && (
                    <button
                      className="collect-stop"
                      disabled={busy || job.cancel_requested}
                      onClick={() => void cancel(job)}
                    >
                      <Square size={13} />
                      Stop collection
                    </button>
                  )}
                  {job.download_available && (
                    <>
                      <div className="collect-verified">
                        <Check size={14} />
                        LeRobot format verified
                      </div>
                      <button
                        className="collect-visualize"
                        onClick={() => {
                          lastViewed.current = job.id;
                          setViewing(job.id);
                          scrollPanel.current?.scrollTo({ top: 0 });
                        }}
                      >
                        <Play size={15} />
                        Visualize dataset
                      </button>
                      <a
                        className="collect-download"
                        href={`/api/collection/jobs/${job.id}/download`}
                        download
                      >
                        <Download size={15} />
                        Download dataset ZIP
                      </a>
                      <p className="collect-path">{job.dataset_path}</p>
                    </>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}
      </div>
      {!viewing && (
        <footer className="look-footer">
          {error && (
            <p className="look-error" role="alert">
              {error}
            </p>
          )}
          {config && !ready && (
            <p>
              Install the collection runtime with{" "}
              <code>bash scripts/setup-collection.sh</code>.
            </p>
          )}
          {!selectedTask && (
            <p>
              Load a task example or choose a pick object and destination first.
            </p>
          )}
          {!editable && (
            <p>Pause the simulation before starting a new collection.</p>
          )}
          {activeJob && (
            <p>A collection is running. See Datasets for progress.</p>
          )}
          <button
            className="look-primary"
            disabled={
              !ready ||
              !valid ||
              !selectedTask ||
              !editable ||
              busy ||
              !!activeJob
            }
            onClick={() => void start()}
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Play size={16} />
            )}
            Start collection
          </button>
          <small className="collect-local">
            Saved locally · no automatic upload
          </small>
        </footer>
      )}
    </aside>
  );
}
