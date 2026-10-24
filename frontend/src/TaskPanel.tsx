import { ArrowRight, Crosshair, FlaskConical, Square, X } from "lucide-react";
import type { Scene, StatePacket, TaskExample } from "./types";
export type PickMode = "source" | "target" | null;
export function TaskPanel({
  scene,
  state,
  editable,
  picking,
  setPicking,
  example,
  examples,
  exampleId,
  setExampleId,
  stop,
}: {
  scene: Scene;
  state: StatePacket | null;
  editable: boolean;
  picking: PickMode;
  setPicking: (v: PickMode) => void;
  example: () => void;
  examples: TaskExample[];
  exampleId: string;
  setExampleId: (id: string) => void;
  stop: () => void;
}) {
  const source = scene.objects.find((o) => o.id === scene.task.source);
  const target = scene.objects.find((o) => o.id === scene.task.target);
  const task = state?.task;
  return (
    <section className="task-panel" aria-label="Task instruction">
      <div className="task-title">
        <span className="eyebrow">TASK INSTRUCTION</span>
        <select
          aria-label="Task example"
          value={exampleId}
          onChange={(e) => setExampleId(e.target.value)}
          disabled={!editable}
        >
          {examples.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
        <button
          className="example-button"
          disabled={!editable}
          onClick={example}
          aria-label="Load task example"
        >
          <FlaskConical size={14} /> Load example
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
              ? "Choose two objects, calculate a path, then Run simulation."
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
      <div className={`plan-feedback ${state?.plan?.status || "idle"}`}>
        <strong data-testid="plan-status">
          {state?.plan?.status === "ready"
            ? `Path ready · ${state.plan.duration.toFixed(1)} s`
            : state?.plan?.status === "calculating"
              ? "Calculating path…"
              : state?.plan?.status === "failed"
                ? "No verified path"
                : "Path not calculated"}
        </strong>
        <span>
          {state?.plan?.message ||
            "Calculate first to preview the gripper movement."}
        </span>
      </div>
      {state?.plan?.status === "calculating" && (
        <button className="cancel-plan" onClick={stop}>
          Cancel calculation
        </button>
      )}
      <div className="task-progress">
        <i style={{ width: `${(task?.progress || 0) * 100}%` }} />
      </div>
      <div className="policy-note">
        IK pick & place{" "}
        <span
          data-testid="grip-physics"
          title="Measured opposing jaw contact forces. Objects are supported by contact and friction; no attachment constraint."
        >
          {task?.graspAssist
            ? "Legacy assisted physics · reconnect to update"
            : task?.held
              ? task.grip?.secure
                ? `Grip confirmed · L ${task.grip.leftForce.toFixed(1)} N / R ${task.grip.rightForce.toFixed(1)} N`
                : "Grip slipping · checking contact"
              : "Contact physics · no attachment"}
        </span>
      </div>
    </section>
  );
}
