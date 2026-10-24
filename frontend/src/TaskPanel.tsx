import { ArrowRight, Crosshair, FlaskConical, Square, X } from "lucide-react";
import type { Scene, StatePacket } from "./types";
export type PickMode = "source" | "target" | null;
export function TaskPanel({
  scene,
  state,
  editable,
  picking,
  setPicking,
  example,
  stop,
}: {
  scene: Scene;
  state: StatePacket | null;
  editable: boolean;
  picking: PickMode;
  setPicking: (v: PickMode) => void;
  example: () => void;
  stop: () => void;
}) {
  const source = scene.objects.find((o) => o.id === scene.task.source);
  const target = scene.objects.find((o) => o.id === scene.task.target);
  const task = state?.task;
  return (
    <section className="task-panel" aria-label="Task instruction">
      <div className="task-title">
        <span className="eyebrow">TASK INSTRUCTION</span>
        <button
          className="example-button"
          disabled={!editable}
          onClick={example}
          aria-label="Load spoon → cup example"
        >
          <FlaskConical size={14} /> Spoon → cup example
        </button>
      </div>
      <div className="task-picks" data-testid="task-instruction">
        <button
          aria-label="Choose pick object"
          className={`task-pick ${picking === "source" ? "choosing" : ""}`}
          disabled={!editable}
          onClick={() => setPicking("source")}
        >
          <span className="step-number">1</span>
          <span>
            <small>PICK OBJECT</small>
            <strong>{source?.name || "Click an object in the scene"}</strong>
          </span>
          <Crosshair size={16} />
        </button>
        <ArrowRight size={18} />
        <button
          aria-label="Choose place object"
          className={`task-pick ${picking === "target" ? "choosing" : ""}`}
          disabled={!editable}
          onClick={() => setPicking("target")}
        >
          <span className="step-number">2</span>
          <span>
            <small>PLACE INTO / ON</small>
            <strong>{target?.name || "Choose a destination"}</strong>
          </span>
          <Crosshair size={16} />
        </button>
      </div>
      {picking ? (
        <div className="pick-prompt">
          Click the {picking === "source" ? "object to pick" : "destination"} in
          any view or the scene collection.
          <button
            aria-label="Cancel task selection"
            onClick={() => setPicking(null)}
          >
            <X size={13} />
          </button>
        </div>
      ) : (
        <div className="task-feedback">
          <span
            data-testid="task-status"
            className={`task-state ${task?.status}`}
          >
            {task?.status === "running" && !state?.running ? "Paused · " : ""}
            {task?.phase || "Ready"}
          </span>
          <span data-testid="task-message">
            {task?.status === "idle"
              ? "Choose two objects, then Run simulation."
              : task?.message}
          </span>
          {task?.status === "running" && (
            <button onClick={stop} aria-label="Stop task">
              <Square size={12} />
              Stop
            </button>
          )}
        </div>
      )}
      <div className="task-progress">
        <i style={{ width: `${(task?.progress || 0) * 100}%` }} />
      </div>
      <div className="policy-note">
        IK pick & place{" "}
        <span>Grasp assist on · success checked after release</span>
      </div>
    </section>
  );
}
