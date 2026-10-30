import { useEffect, useRef, useState } from "react";
import { Search, Upload, GripVertical, Plus, Bot, Table2 } from "lucide-react";
import type { Asset, Scene } from "./types";
export function AssetArt({ id, color }: { id: string; color: string }) {
  id = id.replace("kalas_", "");
  return (
    <svg
      viewBox="0 0 100 76"
      className={`asset-art art-${id}`}
      aria-hidden="true"
    >
      <ellipse cx="51" cy="64" rx="29" ry="6" fill="#000" opacity=".15" />
      {id === "cup" ? (
        <>
          <path d="M27 20L34 59Q50 70 66 59L73 20" fill={color} />
          <ellipse cx="50" cy="20" rx="23" ry="8" fill={color} />
          <ellipse
            cx="50"
            cy="20"
            rx="19"
            ry="5"
            fill="#46372e"
            opacity=".55"
          />
          <path
            d="M33 30L38 55"
            stroke="#fff"
            strokeWidth="4"
            strokeLinecap="round"
            opacity=".25"
          />
        </>
      ) : id === "bowl" ? (
        <>
          <path d="M13 28 Q19 65 50 66 Q81 65 87 28" fill={color} />
          <ellipse cx="50" cy="28" rx="37" ry="16" fill={color} />
          <ellipse cx="50" cy="28" rx="32" ry="12" fill="#000" opacity=".15" />
          <path
            d="M21 35 Q26 56 42 58"
            stroke="#fff"
            strokeWidth="3"
            opacity=".25"
            fill="none"
          />
        </>
      ) : id === "plate" ? (
        <>
          <ellipse cx="50" cy="43" rx="37" ry="16" fill={color} />
          <ellipse cx="50" cy="39" rx="37" ry="16" fill={color} />
          <ellipse
            cx="50"
            cy="39"
            rx="29"
            ry="11"
            stroke="#fff"
            strokeWidth="1.5"
            fill="#000"
            fillOpacity=".12"
            strokeOpacity=".3"
          />
        </>
      ) : id === "spoon" ? (
        <g transform="rotate(-35 50 40)">
          <rect x="15" y="37" width="52" height="7" rx="3.5" fill={color} />
          <ellipse cx="72" cy="40" rx="15" ry="11" fill={color} />
          <ellipse cx="73" cy="38" rx="10" ry="6" fill="#000" opacity=".14" />
        </g>
      ) : (
        <>
          <path d="M24 28L50 15L77 28L50 42Z" fill={color} />
          <path d="M24 28L50 42V66L24 51Z" fill={color} opacity=".7" />
          <path d="M50 42L77 28V51L50 66Z" fill={color} opacity=".9" />
        </>
      )}
    </svg>
  );
}
export interface PlacementCursor {
  x: number;
  y: number;
  drop: boolean;
}
interface Props {
  assets: Asset[];
  storageError?: string;
  retryStorage?: () => void;
  scene: Scene;
  selected: string | null;
  select: (id: string | null) => void;
  add: (id: string) => void;
  editable: boolean;
  onImport: () => void;
  drag: (asset: Asset | null, cursor?: PlacementCursor) => void;
}
export function Library(p: Props) {
  const [query, setQuery] = useState(""),
    [category, setCategory] = useState("All assets");
  const gesture = useRef<{
    id: number;
    x: number;
    y: number;
    active: boolean;
  } | null>(null);
  useEffect(() => {
    const cancel = () => {
      gesture.current = null;
      p.drag(null);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") cancel();
    };
    window.addEventListener("keydown", key);
    window.addEventListener("blur", cancel);
    if (!p.editable) cancel();
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener("blur", cancel);
    };
  }, [p.editable, p.drag]);
  const cats = [
    "All assets",
    "Cups",
    "Bowls",
    "Plates",
    "Spoons",
    "Other Objects",
    "Imported",
  ];
  const filtered = p.assets.filter(
    (a) =>
      (category === "All assets" || a.category === category) &&
      a.name.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <aside className="library sidebar">
      <div className="panel-title">
        <span>ASSET LIBRARY</span>
        <span className="counter">{p.assets.length}</span>
      </div>
      <div className="search">
        <Search size={14} />
        <input
          aria-label="Search assets"
          placeholder="Search objects…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <kbd>⌕</kbd>
      </div>
      <div className="asset-filter">
        <select
          aria-label="Asset category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {cats.map((name) => (
            <option key={name} value={name}>
              {name} (
              {name === "All assets"
                ? p.assets.length
                : p.assets.filter((a) => a.category === name).length}
              )
            </option>
          ))}
        </select>
      </div>
      <div className="section-label">
        OBJECTS <span>DRAG TO PLACE</span>
      </div>
      <button
        className="import-button"
        aria-label="Import object"
        disabled={!p.editable}
        onClick={p.onImport}
      >
        <Upload size={14} /> Import object <span>Mesh · MuJoCo</span>
      </button>
      {p.storageError && (
        <div role="alert" className="library-storage-error">
          <p>{p.storageError}</p>
          <button onClick={p.retryStorage}>Retry library save</button>
        </div>
      )}
      <div className="asset-list">
        {filtered.map((a) => (
          <div
            key={a.id}
            className={`asset-card ${!p.editable ? "disabled" : ""}`}
            draggable={false}
            data-testid={`asset-${a.id}`}
            onDragStart={(e) => e.preventDefault()}
            onPointerDown={(e) => {
              if (
                !p.editable ||
                e.button !== 0 ||
                (e.target as HTMLElement).closest("button")
              )
                return;
              e.preventDefault();
              e.currentTarget.setPointerCapture(e.pointerId);
              gesture.current = {
                id: e.pointerId,
                x: e.clientX,
                y: e.clientY,
                active: false,
              };
            }}
            onPointerMove={(e) => {
              const g = gesture.current;
              if (!g || g.id !== e.pointerId) return;
              if (Math.hypot(e.clientX - g.x, e.clientY - g.y) < 5 && !g.active)
                return;
              g.active = true;
              p.drag(a, { x: e.clientX, y: e.clientY, drop: false });
            }}
            onPointerUp={(e) => {
              const g = gesture.current;
              if (!g || g.id !== e.pointerId) return;
              gesture.current = null;
              if (g.active)
                p.drag(a, { x: e.clientX, y: e.clientY, drop: true });
              else p.drag(null);
            }}
            onPointerCancel={() => {
              gesture.current = null;
              p.drag(null);
            }}
            onLostPointerCapture={() => {
              if (gesture.current) {
                gesture.current = null;
                p.drag(null);
              }
            }}
          >
            <div className="asset-visual">
              <AssetArt id={a.id} color={a.color} />
              <span className="asset-type">
                {a.imported
                  ? "IMPORTED · SAVED"
                  : a.approximate
                    ? "KALAS · APPROX."
                    : "PROCEDURAL"}
              </span>
              <GripVertical size={14} className="grip" />
            </div>
            <div className="asset-meta">
              <div>
                <strong>{a.name}</strong>
                <small>
                  {a.dimensions.map((x) => Math.round(x * 1000)).join(" × ")} mm
                </small>
              </div>
              <button
                disabled={!p.editable}
                title={`Add ${a.name}`}
                aria-label={`Add ${a.name}`}
                onClick={() => p.add(a.id)}
              >
                <Plus size={16} />
              </button>
            </div>
          </div>
        ))}
        {!filtered.length && <p className="quiet">No matching objects.</p>}
      </div>
      <div className="scene-tree">
        <div className="panel-title">
          <span>SCENE COLLECTION</span>
          <span>{p.scene.objects.length + 2}</span>
        </div>
        <button
          className={`tree-row ${p.selected === "robot" ? "selected" : ""}`}
          onClick={() => p.select("robot")}
        >
          <Bot size={15} />
          <span>SO-101 arm</span>
          <small>FIXED</small>
        </button>
        <button
          className={`tree-row ${p.selected === "table" ? "selected" : ""}`}
          onClick={() => p.select("table")}
        >
          <Table2 size={15} />
          <span>Table & environment</span>
        </button>
        {p.scene.objects.map((o) => (
          <button
            data-testid={`object-${o.id}`}
            className={`tree-row ${p.selected === o.id ? "selected" : ""}`}
            key={o.id}
            onClick={() => p.select(o.id)}
          >
            <span className="object-dot" style={{ background: o.color }} />
            <span>{o.name}</span>
          </button>
        ))}
        {!p.scene.objects.length && (
          <p className="tree-empty">Your tabletop is a blank canvas.</p>
        )}
      </div>
      <div className="library-footer">
        <span className="green-dot" />
        Local assets · ready to use
      </div>
    </aside>
  );
}
