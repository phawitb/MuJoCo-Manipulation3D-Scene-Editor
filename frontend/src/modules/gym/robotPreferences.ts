import type { JointInfo } from "./types";

export const foldedJoints = () => [0, -1.5, 1.5, -1.5, 0, 0];
const key = "so101.robot-reset-position";

export function readResetJoints(limits: JointInfo[]): number[] | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) || "null");
    return Array.isArray(value) &&
      value.length === 6 &&
      limits.length === 6 &&
      value.every(
        (v, i) =>
          typeof v === "number" &&
          Number.isFinite(v) &&
          v >= limits[i].min &&
          v <= limits[i].max,
      )
      ? value
      : null;
  } catch {
    return null;
  }
}

// Call only after the server has accepted the pose. Storage failure is surfaced.
export function rememberResetJoints(joints: number[]) {
  localStorage.setItem(key, JSON.stringify(joints));
}

const pedestalKey = "so101.robot-pedestal-height";
export function readPedestalHeight(): number | null {
  try {
    const value: unknown = JSON.parse(
      localStorage.getItem(pedestalKey) || "null",
    );
    return typeof value === "number" &&
      Number.isFinite(value) &&
      value >= 0 &&
      value <= 0.2
      ? value
      : null;
  } catch {
    return null;
  }
}
export function rememberPedestalHeight(height: number) {
  localStorage.setItem(pedestalKey, JSON.stringify(height));
}
