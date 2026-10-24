import { useState } from "react";
import { X } from "lucide-react";
import type { CameraState, ViewKind } from "./types";
export function CameraEditor({
  kind,
  value,
  close,
  apply,
}: {
  kind: ViewKind;
  value: CameraState;
  close: () => void;
  apply: (c: CameraState) => Promise<void>;
}) {
  const [draft, setDraft] = useState(() => ({
    position: value.position.map(String),
    target: value.target.map(String),
    fov: String(value.fov || 50),
    zoom: String(value.zoom),
  }));
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const submit = async () => {
    try {
      const position = draft.position.map(Number) as CameraState["position"],
        target = draft.target.map(Number) as CameraState["target"];
      const fov = Number(draft.fov),
        zoom = Number(draft.zoom);
      if (
        [...draft.position, ...draft.target, draft.fov, draft.zoom].some(
          (v) => !v.trim(),
        ) ||
        ![...position, ...target, fov, zoom].every(Number.isFinite) ||
        Math.hypot(...position.map((v, i) => v - target[i])) < 0.01
      )
        throw Error(
          "Enter finite coordinates with camera and target at least 1 cm apart.",
        );
      if (fov < 15 || fov > 100 || zoom <= 0 || zoom > 10000)
        throw Error("Field of view: 15–100°. Zoom must be positive.");
      setBusy(true);
      await apply({ position, target, fov, zoom });
      close();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop">
      <div
        className="workbench-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Edit camera"
      >
        <button
          className="close"
          onClick={close}
          aria-label="Close camera editor"
        >
          <X size={18} />
        </button>
        <span className="eyebrow">CAMERA SETTINGS</span>
        <h2>{kind[0].toUpperCase() + kind.slice(1)} view</h2>
        <p>Position and look-at target in meters. Z points up.</p>
        {(["position", "target"] as const).map((group) => (
          <fieldset key={group}>
            <legend>
              {group === "position" ? "Camera position" : "Look-at target"}
            </legend>
            <div className="vector-fields">
              {["X", "Y", "Z"].map((axis, i) => (
                <label key={axis}>
                  {axis}
                  <input
                    aria-label={`Camera ${group} ${axis}`}
                    type="number"
                    step=".01"
                    value={draft[group][i]}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        [group]: draft[group].map((v, n) =>
                          n === i ? e.target.value : v,
                        ),
                      })
                    }
                  />
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <label>
          Field of view (degrees)
          <input
            aria-label="Camera field of view"
            type="number"
            min="15"
            max="100"
            value={draft.fov}
            onChange={(e) => setDraft({ ...draft, fov: e.target.value })}
          />
        </label>
        {kind === "top" && (
          <label>
            Zoom
            <input
              type="number"
              value={draft.zoom}
              onChange={(e) => setDraft({ ...draft, zoom: e.target.value })}
            />
          </label>
        )}
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <button
          className="primary-action"
          disabled={busy}
          onClick={() => void submit()}
        >
          {busy ? "Applying…" : "Apply camera"}
        </button>
      </div>
    </div>
  );
}
