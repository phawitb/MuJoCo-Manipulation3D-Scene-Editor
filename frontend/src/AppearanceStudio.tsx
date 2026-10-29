import { useEffect, useRef, useState } from "react";
import {
  Download,
  Palette,
  Shuffle,
  SlidersHorizontal,
  Sun,
  X,
} from "lucide-react";
import type {
  Appearance,
  AppearanceGroup,
  AppearancePreset,
  Pattern,
  Randomization,
  Scene,
  Snapshot,
  Surface,
} from "./types";

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
const scopes: AppearanceGroup[] = [
  "robot",
  "table",
  "environment",
  "lighting",
  "objects",
];

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="look-color">
      <span>{label}</span>
      <span>
        <code>{value.toUpperCase()}</code>
        <input
          type="color"
          aria-label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </span>
    </label>
  );
}
function RangeField({
  label,
  value,
  min,
  max,
  step = 0.01,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="look-range">
      <span>
        {label}
        <output>{Number(value.toFixed(2))}</output>
      </span>
      <input
        aria-label={label}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
function SurfaceFields({
  name,
  value,
  color,
  onChange,
  onColor,
}: {
  name: string;
  value: Surface;
  color: string;
  onChange: (v: Surface) => void;
  onColor: (v: string) => void;
}) {
  return (
    <section className="look-section">
      <h3>
        {name}
        <span>SURFACE</span>
      </h3>
      <ColorField label={`${name} color`} value={color} onChange={onColor} />
      <label className="look-select">
        Pattern
        <select
          aria-label={`${name} pattern`}
          value={value.pattern}
          onChange={(e) =>
            onChange({ ...value, pattern: e.target.value as Pattern })
          }
        >
          {patterns.map((p) => (
            <option key={p} value={p}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </option>
          ))}
        </select>
      </label>
      {value.pattern !== "solid" && (
        <>
          <ColorField
            label={`${name} accent`}
            value={value.secondary}
            onChange={(secondary) => onChange({ ...value, secondary })}
          />
          <RangeField
            label={`${name} pattern scale`}
            value={value.repeat}
            min={1}
            max={24}
            step={0.1}
            onChange={(repeat) => onChange({ ...value, repeat })}
          />
        </>
      )}
      <RangeField
        label={`${name} roughness`}
        value={value.roughness}
        min={0.05}
        max={1}
        onChange={(roughness) => onChange({ ...value, roughness })}
      />
      <RangeField
        label={`${name} metallic`}
        value={value.metallic}
        min={0}
        max={1}
        onChange={(metallic) => onChange({ ...value, metallic })}
      />
    </section>
  );
}
interface Props {
  scene: Scene;
  editable: boolean;
  currentScene: () => Scene;
  apply: (value: Appearance, tableColor: string) => Promise<unknown>;
  randomize: (value: Randomization) => Promise<unknown>;
  close: () => void;
}
export function AppearanceStudio({
  scene,
  editable,
  currentScene,
  apply,
  randomize,
  close,
}: Props) {
  const [draft, setDraft] = useState(() => structuredClone(scene.appearance!));
  const [tableColor, setTableColor] = useState(scene.table.color || "#b8c2bf");
  const [presets, setPresets] = useState<AppearancePreset[]>([]);
  const [tab, setTab] = useState("surfaces");
  const [dirty, setDirty] = useState(false);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [seed, setSeed] = useState(
    scene.appearance?.last_randomization?.seed ?? 42,
  );
  const [groups, setGroups] = useState<AppearanceGroup[]>([...scopes]);
  const [strength, setStrength] =
    useState<Randomization["strength"]>("balanced");
  const [count, setCount] = useState(8);
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close();
      }
    };
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("keydown", escape);
      previous?.focus();
    };
  }, [close]);
  useEffect(() => {
    const abort = new AbortController();
    fetch("/api/appearance/presets", { signal: abort.signal })
      .then((r) => {
        if (!r.ok) throw Error("Could not load appearance presets");
        return r.json();
      })
      .then(setPresets)
      .catch((e) => {
        if (!abort.signal.aborted) setError(String(e));
      });
    return () => abort.abort();
  }, []);
  // Snapshot object identities change even when only the camera changes.
  const savedAppearance = JSON.stringify(scene.appearance);
  useEffect(() => {
    if (savedAppearance) setDraft(JSON.parse(savedAppearance));
    setTableColor(scene.table.color || "#b8c2bf");
    setDirty(false);
  }, [savedAppearance, scene.table.color]);
  const update = <K extends keyof Appearance>(key: K, value: Appearance[K]) => {
    setDraft((d) => ({ ...d, [key]: value, last_randomization: null }));
    setDirty(true);
    setMessage("");
  };
  const run = async (operation: () => Promise<unknown>, success: string) => {
    setWorking(true);
    setError("");
    setMessage("");
    try {
      const result = await operation();
      // An identical preset produces no content change, but must still replace
      // any unapplied draft. Use the server-confirmed result in both cases.
      if (result && typeof result === "object" && "scene" in result) {
        const confirmed = (result as Snapshot).scene;
        if (confirmed.appearance)
          setDraft(structuredClone(confirmed.appearance));
        setTableColor(confirmed.table.color || "#b8c2bf");
      }
      setMessage(success);
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setWorking(false);
    }
  };
  const disabled = !editable || working;
  const validSeed = Number.isInteger(seed) && seed >= 0 && seed <= 2147483647;
  const randomDisabled = disabled || !validSeed || !groups.length;
  const exportRecipes = async () => {
    const response = await fetch("/api/appearance/variants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scene: currentScene(),
        seed,
        groups,
        strength,
        count,
      }),
    });
    if (!response.ok) {
      const body = await response.json();
      throw Error(
        typeof body.detail === "string"
          ? body.detail
          : "Invalid recipe settings",
      );
    }
    const data = await response.json();
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `appearance-recipes-${seed}-${count}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <aside className="appearance-studio" aria-label="Appearance Studio panel">
      <header className="look-header">
        <div className="look-icon">
          <Palette size={22} />
        </div>
        <div>
          <small>VISUAL DOMAIN RANDOMIZATION</small>
          <h2>Appearance Studio</h2>
        </div>
        <button
          ref={closeButton}
          onClick={close}
          aria-label="Close Appearance Studio"
        >
          <X size={19} />
        </button>
      </header>
      <div className="look-intro">
        Build many worlds around the same task.
        <span>
          Shared with MuJoCo camera observations · saved in your scene.
        </span>
      </div>
      <nav className="look-tabs" aria-label="Appearance categories">
        {[
          { id: "surfaces", name: "Surfaces", Icon: Palette },
          { id: "environment", name: "World", Icon: SlidersHorizontal },
          { id: "lighting", name: "Light", Icon: Sun },
          { id: "randomize", name: "Randomize", Icon: Shuffle },
        ].map(({ id, name, Icon }) => (
          <button key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>
            <Icon size={15} />
            {name}
          </button>
        ))}
      </nav>
      <div className="look-scroll">
        <fieldset disabled={disabled}>
          {tab === "surfaces" && (
            <>
              <section className="look-section">
                <h3>
                  Start with a look<span>6 PRESETS</span>
                </h3>
                <div className="look-presets">
                  {presets.map((p) => (
                    <button
                      key={p.id}
                      aria-label={p.name}
                      onClick={() =>
                        void run(
                          () => apply(p.appearance, p.tableColor),
                          `${p.name} applied`,
                        )
                      }
                    >
                      <span
                        className="look-preview"
                        style={{
                          background: `linear-gradient(150deg, ${p.appearance.background} 0% 45%, ${p.tableColor} 45% 76%, ${p.appearance.floor_color} 76%)`,
                        }}
                      >
                        <i style={{ background: p.appearance.robot_color }} />
                      </span>
                      <strong>{p.name}</strong>
                      <small>{p.description}</small>
                    </button>
                  ))}
                </div>
              </section>
              <SurfaceFields
                name="Table"
                value={draft.table}
                color={tableColor}
                onColor={(v) => {
                  setTableColor(v);
                  update("last_randomization", null);
                }}
                onChange={(v) => update("table", v)}
              />
              <SurfaceFields
                name="Robot"
                value={draft.robot}
                color={draft.robot_color}
                onColor={(v) => update("robot_color", v)}
                onChange={(v) => update("robot", v)}
              />
              <section className="look-section">
                <h3>Details</h3>
                <ColorField
                  label="Motor color"
                  value={draft.motor_color}
                  onChange={(v) => update("motor_color", v)}
                />
                <ColorField
                  label="Table legs color"
                  value={draft.leg_color}
                  onChange={(v) => update("leg_color", v)}
                />
              </section>
            </>
          )}
          {tab === "environment" && (
            <>
              <section className="look-section">
                <h3>
                  Surroundings<span>VISUAL ONLY</span>
                </h3>
                <label className="look-select">
                  Environment
                  <select
                    aria-label="Environment type"
                    value={draft.environment}
                    onChange={(e) =>
                      update(
                        "environment",
                        e.target.value as Appearance["environment"],
                      )
                    }
                  >
                    {["open", "studio", "room", "warehouse", "panels"].map(
                      (v) => (
                        <option key={v} value={v}>
                          {v.charAt(0).toUpperCase() + v.slice(1)}
                        </option>
                      ),
                    )}
                  </select>
                </label>
                <p>
                  Walls, shelving and panels stay outside the worktable and do
                  not participate in collisions.
                </p>
                <ColorField
                  label="Background color"
                  value={draft.background}
                  onChange={(v) => update("background", v)}
                />
              </section>
              <SurfaceFields
                name="Floor"
                value={draft.floor}
                color={draft.floor_color}
                onColor={(v) => update("floor_color", v)}
                onChange={(v) => update("floor", v)}
              />
              <SurfaceFields
                name="Wall"
                value={draft.wall}
                color={draft.wall_color}
                onColor={(v) => update("wall_color", v)}
                onChange={(v) => update("wall", v)}
              />
            </>
          )}
          {tab === "lighting" && (
            <>
              <section className="look-section">
                <h3>
                  Key light<span>DIRECTIONAL</span>
                </h3>
                <ColorField
                  label="Light color"
                  value={draft.key_color}
                  onChange={(v) => update("key_color", v)}
                />
                <RangeField
                  label="Key intensity"
                  value={draft.key_intensity}
                  min={0}
                  max={2.5}
                  onChange={(v) => update("key_intensity", v)}
                />
                <RangeField
                  label="Light azimuth"
                  value={draft.light_azimuth}
                  min={-180}
                  max={180}
                  step={1}
                  onChange={(v) => update("light_azimuth", v)}
                />
                <RangeField
                  label="Light elevation"
                  value={draft.light_elevation}
                  min={15}
                  max={85}
                  step={1}
                  onChange={(v) => update("light_elevation", v)}
                />
                <label className="look-check">
                  <input
                    type="checkbox"
                    checked={draft.shadows}
                    onChange={(e) => update("shadows", e.target.checked)}
                  />
                  Cast shadows
                </label>
              </section>
              <section className="look-section">
                <h3>Fill & ambient</h3>
                <RangeField
                  label="Fill intensity"
                  value={draft.fill_intensity}
                  min={0}
                  max={1.5}
                  onChange={(v) => update("fill_intensity", v)}
                />
                <RangeField
                  label="Ambient intensity"
                  value={draft.ambient}
                  min={0.05}
                  max={1}
                  onChange={(v) => update("ambient", v)}
                />
                <p>
                  The web preview and native camera share light settings. Their
                  shading is approximate, not pixel-identical.
                </p>
              </section>
            </>
          )}
          {tab === "randomize" && (
            <>
              <section className="look-section">
                <h3>
                  Reproducible variation<span>GENERATOR 1</span>
                </h3>
                <p>
                  Use a seed to repeat a look. Unchecked categories retain their
                  current settings.
                </p>
                <label className="look-select">
                  Random seed
                  <input
                    aria-label="Random seed"
                    type="number"
                    min={0}
                    max={2147483647}
                    step={1}
                    value={Number.isNaN(seed) ? "" : seed}
                    onChange={(e) => setSeed(e.target.valueAsNumber)}
                  />
                </label>
                <label className="look-select">
                  Variation range
                  <select
                    aria-label="Variation range"
                    value={strength}
                    onChange={(e) =>
                      setStrength(e.target.value as Randomization["strength"])
                    }
                  >
                    <option value="mild">
                      Mild · muted colors & simple patterns
                    </option>
                    <option value="balanced">
                      Balanced · diverse everyday looks
                    </option>
                    <option value="wide">
                      Wide · bold patterns & contrast
                    </option>
                  </select>
                </label>
                <div className="look-scopes">
                  {scopes.map((group) => (
                    <label key={group} className="look-check">
                      <input
                        aria-label={`Randomize ${group}`}
                        type="checkbox"
                        checked={groups.includes(group)}
                        onChange={(e) =>
                          setGroups((old) =>
                            e.target.checked
                              ? [...old, group]
                              : old.filter((g) => g !== group),
                          )
                        }
                      />
                      {group.charAt(0).toUpperCase() + group.slice(1)}
                    </label>
                  ))}
                </div>
                <div className="look-row">
                  <button
                    disabled={randomDisabled || dirty}
                    onClick={() =>
                      void run(
                        () => randomize({ seed, groups, strength }),
                        `Applied seed ${seed}`,
                      )
                    }
                  >
                    Apply seed
                  </button>
                  <button
                    className="look-primary"
                    disabled={disabled || !groups.length || dirty}
                    onClick={() => {
                      const next =
                        crypto.getRandomValues(new Uint32Array(1))[0] %
                        2147483648;
                      setSeed(next);
                      void run(
                        () => randomize({ seed: next, groups, strength }),
                        `Applied seed ${next}`,
                      );
                    }}
                  >
                    <Shuffle size={15} />
                    New variation
                  </button>
                </div>
                {dirty && (
                  <p>Apply your surface edits first, then randomize.</p>
                )}
                <p>
                  Only visual properties change. Robot motion, cameras, object
                  placement, mass and friction stay fixed.
                </p>
              </section>
              <section className="look-section">
                <h3>
                  Recipe batch<span>FOR DATA COLLECTION</span>
                </h3>
                <p>
                  Export portable scenes for consecutive seeds. This creates
                  scene recipes; it does not record images or trajectories.
                </p>
                <label className="look-select">
                  Number of recipes
                  <input
                    aria-label="Number of recipes"
                    type="number"
                    min={1}
                    max={32}
                    value={Number.isNaN(count) ? "" : count}
                    onChange={(e) => setCount(e.target.valueAsNumber)}
                  />
                </label>
                <button
                  className="look-export"
                  disabled={
                    randomDisabled ||
                    dirty ||
                    !Number.isInteger(count) ||
                    count < 1 ||
                    count > 32 ||
                    seed + count - 1 > 2147483647
                  }
                  onClick={() =>
                    void run(exportRecipes, `Exported ${count} recipes`)
                  }
                >
                  <Download size={15} />
                  Export recipes
                </button>
                <p>
                  Keep held-out environments for evaluation. More visual
                  variation alone does not establish robustness.
                </p>
              </section>
            </>
          )}
        </fieldset>
      </div>
      <footer className="look-footer">
        {!editable && !working && (
          <p>Pause the simulation to edit its appearance.</p>
        )}
        {error && (
          <p role="alert" className="look-error">
            {error}
          </p>
        )}
        <div role="status">
          {working
            ? "Updating scene…"
            : message ||
              (dirty
                ? "Unapplied changes"
                : "All settings saved in this scene")}
        </div>
        <button
          className="look-primary"
          disabled={disabled || !dirty}
          onClick={() =>
            void run(() => apply(draft, tableColor), "Appearance applied")
          }
        >
          <Palette size={16} />
          Apply appearance
        </button>
      </footer>
    </aside>
  );
}
