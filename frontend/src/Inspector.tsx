import { useEffect, useState, useMemo } from "react";
import {
  Box,
  Bot,
  ChevronDown,
  Copy,
  Focus,
  Info,
  SlidersHorizontal,
  Table2,
  Trash2,
} from "lucide-react";
import type { Asset, JointInfo, Scene, SceneObject, Vec3 } from "./types";
import { fromDegrees, rotationDegrees } from "./math";
import { AssetArt } from "./Library";

function NumberField({
  value,
  onCommit,
  label,
  step = 0.01,
  min,
  max,
  disabled = false,
}: {
  value: number;
  onCommit: (v: number) => void;
  label: string;
  step?: number;
  min?: number;
  max?: number;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState(String(Number(value.toFixed(4))));
  useEffect(() => setDraft(String(Number(value.toFixed(4)))), [value]);
  return (
    <label className="number-field">
      <span>{label}</span>
      <input
        type="number"
        aria-label={label}
        step={step}
        min={min}
        max={max}
        disabled={disabled}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
        }}
        onBlur={() => {
          const v = Number(draft);
          if (
            draft !== "" &&
            Number.isFinite(v) &&
            v !== value &&
            (min === undefined || v >= min) &&
            (max === undefined || v <= max)
          )
            onCommit(v);
          // Only an acknowledged value is shown after committing a draft.
          setDraft(String(Number(value.toFixed(4))));
        }}
      />
    </label>
  );
}
function VectorFields({
  label,
  value,
  onCommit,
  disabled,
  step = 0.01,
}: {
  label: string;
  value: Vec3;
  onCommit: (v: Vec3) => void;
  disabled: boolean;
  step?: number;
}) {
  return (
    <>
      <div className="field-heading">
        {label}
        <span>{label.includes("Rotation") ? "DEG" : "m"}</span>
      </div>
      <div className="vector-fields">
        {value.map((v, i) => (
          <NumberField
            key={i}
            label={`${label} ${"XYZ"[i]}`}
            value={v}
            disabled={disabled}
            step={step}
            onCommit={(n) => {
              const next = [...value] as Vec3;
              next[i] = n;
              onCommit(next);
            }}
          />
        ))}
      </div>
    </>
  );
}
function JointControl({
  value,
  info,
  index,
  disabled,
  onCommit,
}: {
  value: number;
  info: JointInfo;
  index: number;
  disabled: boolean;
  onCommit: (v: number) => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return (
    <div className="joint-control">
      <div>
        <span className="joint-index">J{index + 1}</span>
        <strong>{info.name.replaceAll("_", " ")}</strong>
        <span>{((draft * 180) / Math.PI).toFixed(1)}°</span>
      </div>
      <input
        aria-label={`${info.name} slider`}
        type="range"
        min={info.min}
        max={info.max}
        step={0.001}
        disabled={disabled}
        value={draft}
        onChange={(e) => setDraft(Number(e.target.value))}
        onPointerUp={() => {
          if (draft !== value) onCommit(draft);
          setDraft(value);
        }}
        onKeyUp={() => {
          if (draft !== value) onCommit(draft);
          setDraft(value);
        }}
      />
      <div className="joint-limits">
        <small>{((info.min * 180) / Math.PI).toFixed(0)}°</small>
        <small>{((info.max * 180) / Math.PI).toFixed(0)}°</small>
      </div>
    </div>
  );
}
interface Props {
  scene: Scene;
  selected: string | null;
  assets: Asset[];
  joints: JointInfo[];
  editable: boolean;
  patchObject: (id: string, patch: Partial<SceneObject>) => void;
  editScene: (fn: (s: Scene) => void) => void;
  remove: () => void;
  duplicate: () => void;
  frame: () => void;
}
export function Inspector(p: Props) {
  const object = p.scene.objects.find((o) => o.id === p.selected);
  const importedAsset = useMemo<Asset | undefined>(() => {
    if (!object?.mesh) return;
    const dimensions = [0, 1, 2].map((axis) => {
      let min = Infinity,
        max = -Infinity;
      for (let i = axis; i < object.mesh!.vertices.length; i += 3) {
        min = Math.min(min, object.mesh!.vertices[i]);
        max = Math.max(max, object.mesh!.vertices[i]);
      }
      return max - min;
    }) as Vec3;
    return {
      id: "mesh",
      name: object.name,
      category: "Imported",
      dimensions,
      mass: object.mass,
      color: object.color,
      description: "Imported mesh · convex hull collision",
    };
  }, [object?.mesh]);
  const asset = p.assets.find((a) => a.id === object?.asset) || importedAsset;
  const disabled = !p.editable;
  return (
    <aside className="inspector sidebar">
      <div className="panel-title">
        <span>INSPECTOR</span>
        <SlidersHorizontal size={14} />
      </div>
      {!p.selected ? (
        <div className="empty-inspector">
          <div className="selection-icon">
            <Box size={30} strokeWidth={1} />
          </div>
          <h3>A space for possibilities.</h3>
          <p>
            Drag an object onto the table to begin. Select anything in the scene
            to inspect its properties.
          </p>
          <div className="quick-guide">
            <span>01</span>
            <div>
              <strong>Build your scene</strong>
              <p>Place cups, plates and tools.</p>
            </div>
            <span>02</span>
            <div>
              <strong>Make it precise</strong>
              <p>Move, rotate and adjust properties.</p>
            </div>
            <span>03</span>
            <div>
              <strong>Run a task</strong>
              <p>Choose pick & place objects, then Run.</p>
            </div>
          </div>
        </div>
      ) : object && asset ? (
        <>
          <div className="selected-card">
            <div className="selected-thumb">
              <AssetArt id={asset.id} color={object.color} />
            </div>
            <div>
              <small>RIGID BODY</small>
              <h3>{object.name}</h3>
              <span>
                {object.mesh
                  ? "Imported / convex hull"
                  : `${object.asset} / procedural`}
              </span>
            </div>
          </div>
          <div className="inspector-scroll">
            <section className="inspector-section">
              <h4>
                Object <ChevronDown size={13} />
              </h4>
              <label className="text-field">
                Name
                <input
                  aria-label="Object name"
                  key={object.id + object.name}
                  defaultValue={object.name}
                  maxLength={80}
                  disabled={disabled}
                  onBlur={(e) => {
                    if (e.target.value.trim() && e.target.value !== object.name)
                      p.patchObject(object.id, { name: e.target.value.trim() });
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") e.currentTarget.blur();
                  }}
                />
              </label>
              <div className="property-row">
                <span>Object ID</span>
                <code>{object.id}</code>
              </div>
              <div className="property-row">
                <span>Asset identifier</span>
                <code>{asset.id}</code>
              </div>
            </section>
            <section className="inspector-section">
              <h4>
                Transform <span>WORLD SPACE</span>
              </h4>
              <VectorFields
                label="Position"
                value={object.position}
                disabled={disabled}
                onCommit={(position) => p.patchObject(object.id, { position })}
              />
              <VectorFields
                label="Rotation"
                value={rotationDegrees(object.quaternion)}
                step={1}
                disabled={disabled}
                onCommit={(v) =>
                  p.patchObject(object.id, { quaternion: fromDegrees(v) })
                }
              />
              <NumberField
                label="Uniform scale"
                value={object.scale}
                min={0.25}
                max={3}
                step={0.05}
                disabled={disabled}
                onCommit={(scale) => p.patchObject(object.id, { scale })}
              />
              <div className="property-row dimensions">
                <span>Dimensions</span>
                <code>
                  {asset.dimensions
                    .map((x) => (x * object.scale * 1000).toFixed(0))
                    .join(" × ")}{" "}
                  mm
                </code>
              </div>
            </section>
            <section className="inspector-section">
              <h4>
                Physics <span>MUJOCO</span>
              </h4>
              <NumberField
                label="Mass (kg)"
                value={object.mass}
                min={0.001}
                max={10}
                step={0.005}
                disabled={disabled}
                onCommit={(mass) => p.patchObject(object.id, { mass })}
              />
              <div className="field-heading">
                Friction <span>CONTACT</span>
              </div>
              {["Sliding", "Torsional", "Rolling"].map((label, i) => (
                <NumberField
                  key={label}
                  label={label}
                  value={object.friction[i]}
                  min={0}
                  max={5}
                  step={i === 0 ? 0.05 : 0.0001}
                  disabled={disabled}
                  onCommit={(v) => {
                    const f = [...object.friction] as Vec3;
                    f[i] = v;
                    p.patchObject(object.id, { friction: f });
                  }}
                />
              ))}
              <label className="toggle-row">
                Collision enabled
                <input
                  type="checkbox"
                  aria-label="Collision enabled"
                  checked={object.collision}
                  disabled={disabled}
                  onChange={(e) =>
                    p.patchObject(object.id, { collision: e.target.checked })
                  }
                />
              </label>
              <label className="toggle-row">
                Surface color
                <input
                  type="color"
                  aria-label="Surface color"
                  value={object.color}
                  disabled={disabled}
                  onChange={(e) =>
                    p.patchObject(object.id, { color: e.target.value })
                  }
                />
              </label>
            </section>
            <p className="info-note">
              <Info size={13} />
              Procedural approximation. Scaling updates visual and collision
              geometry together.
            </p>
          </div>
          <div className="inspector-actions">
            <button onClick={p.frame}>
              <Focus size={15} />
              Frame
            </button>
            <button
              disabled={disabled}
              onClick={p.duplicate}
              aria-label="Duplicate object"
            >
              <Copy size={15} />
            </button>
            <button
              className="danger"
              disabled={disabled}
              onClick={p.remove}
              aria-label="Delete object"
            >
              <Trash2 size={15} />
            </button>
          </div>
        </>
      ) : p.selected === "robot" ? (
        <>
          <div className="selected-card">
            <div className="selected-thumb robot-thumb">
              <Bot size={30} />
            </div>
            <div>
              <small>6-AXIS MANIPULATOR</small>
              <h3>SO-101</h3>
              <span>The Robot Studio · fixed base</span>
            </div>
          </div>
          <div className="inspector-scroll">
            <section className="inspector-section">
              <h4>
                Joint positions <span>DEGREES</span>
              </h4>
              {p.joints.map((joint, i) => (
                <JointControl
                  key={joint.name}
                  info={joint}
                  index={i}
                  value={p.scene.robot.joints[i]}
                  disabled={disabled}
                  onCommit={(v) =>
                    p.editScene((s) => {
                      s.robot.joints[i] = v;
                    })
                  }
                />
              ))}
            </section>
            <section className="inspector-section">
              <h4>Base transform</h4>
              <VectorFields
                label="Base position"
                value={p.scene.robot.position}
                disabled={disabled}
                onCommit={(v) =>
                  p.editScene((s) => {
                    s.robot.position = v;
                  })
                }
              />
              <VectorFields
                label="Base Rotation"
                value={rotationDegrees(p.scene.robot.quaternion)}
                disabled={disabled}
                step={1}
                onCommit={(v) =>
                  p.editScene((s) => {
                    s.robot.quaternion = fromDegrees(v);
                  })
                }
              />
            </section>
            <p className="info-note">
              <Info size={13} />
              Real SO-101 model from MuJoCo Menagerie. Position-controlled
              joints; fixed base.
            </p>
          </div>
        </>
      ) : (
        <>
          <div className="selected-card">
            <div className="selected-thumb">
              <Table2 size={30} />
            </div>
            <div>
              <small>ENVIRONMENT</small>
              <h3>Worktable</h3>
              <span>Static body · Z-up world</span>
            </div>
          </div>
          <section className="inspector-section">
            <h4>Dimensions</h4>
            {(["width", "depth", "height"] as const).map((key) => (
              <NumberField
                key={key}
                label={`Table ${key} (m)`}
                value={p.scene.table[key]}
                min={0.4}
                max={key === "height" ? 1.2 : 2}
                disabled={disabled}
                onCommit={(v) =>
                  p.editScene((s) => {
                    if (key === "height")
                      s.robot.position[2] += v - s.table.height;
                    s.table[key] = v;
                  })
                }
              />
            ))}
            <p className="info-note">
              Table height moves the robot mount with it. Existing objects keep
              their world positions.
            </p>
          </section>
        </>
      )}
      <div className="inspector-footer">
        <span>WORLD COORDINATES</span>
        <div>
          <i className="axis-x">X</i>
          <i className="axis-y">Y</i>
          <i className="axis-z">Z</i>
          <span>Meters / degrees</span>
        </div>
      </div>
    </aside>
  );
}
