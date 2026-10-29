import type { Pattern } from "./types";
export type PaletteKey =
  | "robot_colors"
  | "motor_colors"
  | "table_colors"
  | "leg_colors"
  | "floor_colors"
  | "wall_colors"
  | "background_colors"
  | "object_colors";
export type PatternKey =
  "robot_patterns" | "table_patterns" | "floor_patterns" | "wall_patterns";
export interface Variation
  extends Record<PaletteKey, string[]>, Record<PatternKey, Pattern[]> {
  environments: string[];
  lighting: boolean;
  finishes: boolean;
  repeat_min: number;
  repeat_max: number;
}
export interface CollectionConfig {
  name: string;
  task: string;
  episodes: number;
  seed: number;
  fps: number;
  resolution: string;
  max_seconds: number;
  include_failed: boolean;
  variation: Variation;
}
export interface CollectionJob {
  id: string;
  name: string;
  status: string;
  episode: number;
  episodes: number;
  saved_episodes: number;
  frames: number;
  total_frames: number;
  seed: number;
  message: string;
  simulation_time?: number;
  updated_at?: number;
  dataset_path: string;
  cancel_requested: boolean;
  download_available: boolean;
  verified: boolean;
}
export const paletteRules: {
  key: PaletteKey;
  name: string;
  defaults: string[];
}[] = [
  { key: "robot_colors", name: "Robot", defaults: ["#f1792e", "#ffd11f"] },
  {
    key: "table_colors",
    name: "Table",
    defaults: ["#ffffff", "#808080", "#202020"],
  },
  { key: "motor_colors", name: "Motor", defaults: ["#202020", "#808080"] },
  { key: "leg_colors", name: "Table legs", defaults: ["#202020", "#808080"] },
  {
    key: "floor_colors",
    name: "Floor",
    defaults: ["#ffffff", "#808080", "#202020"],
  },
  { key: "wall_colors", name: "Wall", defaults: ["#ffffff", "#808080"] },
  {
    key: "background_colors",
    name: "Background",
    defaults: ["#ffffff", "#808080", "#202020"],
  },
  {
    key: "object_colors",
    name: "Object",
    defaults: ["#f1792e", "#ffd11f", "#668ad5"],
  },
];
export const patternRules: { key: PatternKey; name: string }[] = [
  { key: "robot_patterns", name: "Robot" },
  { key: "table_patterns", name: "Table" },
  { key: "floor_patterns", name: "Floor" },
  { key: "wall_patterns", name: "Wall" },
];
export const terminalStatuses = [
  "completed",
  "cancelled",
  "failed",
  "interrupted",
];
