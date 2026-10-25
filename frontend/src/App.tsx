import { lazy, Suspense, useState, type ComponentType } from "react";
import { Box, Cable, Cuboid } from "lucide-react";
import {
  enabledModules,
  selectedModule,
  type ModuleId,
} from "./modules/registry";
import type { ModuleProps, RobotControlProps } from "./modules/types";
const entries = import.meta.glob<{
  default: ComponentType<ModuleProps>;
  GymRobot?: ComponentType<RobotControlProps>;
}>("./modules/*/index.ts");
const panels = Object.fromEntries(
  Object.entries(entries).map(([path, load]) => [
    path.split("/")[2],
    lazy(load),
  ]),
) as Record<ModuleId, ReturnType<typeof lazy<ComponentType<ModuleProps>>>>;
const connectionEntry = entries["./modules/connection/index.ts"];
const RobotControls = connectionEntry
  ? lazy(async () => {
      const module = await connectionEntry();
      return { default: module.GymRobot || (() => null) };
    })
  : undefined;
const labels = {
  gym: "Gym",
  connection: "Setting Connection",
  blender: "Blender",
};
const icons = { gym: Box, connection: Cable, blender: Cuboid };
const config = (import.meta as ImportMeta & { env: Record<string, string> }).env
  .VITE_STUDIO_MODULES;
export default function App() {
  const available = enabledModules(config).filter((id) => id in panels);
  if (!available.length)
    throw new Error("No installed studio modules match this deployment.");
  const [active, setActive] = useState<ModuleId>(() => {
    let saved = null;
    try {
      saved = localStorage.getItem("studio.activeTab");
    } catch {}
    return selectedModule(saved, available);
  });
  const [visited, setVisited] = useState<Set<ModuleId>>(
    () => new Set([active]),
  );
  const choose = (id: ModuleId) => {
    setActive(id);
    setVisited((old) => new Set([...old, id]));
    try {
      localStorage.setItem("studio.activeTab", id);
    } catch {}
  };
  return (
    <div className="studio-shell">
      <nav className="studio-tabs" role="tablist" aria-label="Studio modules">
        <span className="studio-tabs-label">SCENE STUDIO</span>
        {available.map((id) => {
          const Icon = icons[id];
          return (
            <button
              key={id}
              id={`tab-${id}`}
              role="tab"
              aria-selected={active === id}
              aria-controls={`panel-${id}`}
              onClick={() => choose(id)}
            >
              <Icon size={16} />
              {labels[id]}
            </button>
          );
        })}
      </nav>
      {available
        .filter((id) => visited.has(id))
        .map((id) => {
          const Panel = panels[id];
          return (
            <section
              key={id}
              className="studio-tab-panel"
              id={`panel-${id}`}
              role="tabpanel"
              aria-labelledby={`tab-${id}`}
              hidden={active !== id}
            >
              <Suspense
                fallback={
                  <p className="module-loading">Loading {labels[id]}…</p>
                }
              >
                <Panel
                  activeTab={active === id}
                  robotControls={
                    id === "gym" && available.includes("connection")
                      ? RobotControls
                      : undefined
                  }
                />
              </Suspense>
            </section>
          );
        })}
    </div>
  );
}
