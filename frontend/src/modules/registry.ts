export const moduleIds = ["gym", "connection", "blender"] as const;
export type ModuleId = (typeof moduleIds)[number];
export function enabledModules(config?: string): ModuleId[] {
  if (config === undefined || config.trim() === "") return [...moduleIds];
  const requested = config.split(",").map((x) => x.trim());
  const result = moduleIds.filter((id) => requested.includes(id));
  if (!result.length)
    throw new Error(
      "No studio modules enabled. Set VITE_STUDIO_MODULES to gym,connection,blender.",
    );
  return result;
}
export function selectedModule(
  saved: string | null,
  available: ModuleId[],
): ModuleId {
  return available.includes(saved as ModuleId)
    ? (saved as ModuleId)
    : available[0];
}
