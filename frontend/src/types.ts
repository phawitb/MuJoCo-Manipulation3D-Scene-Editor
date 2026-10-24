export type Vec3 = [number, number, number];
export type Quat = [number, number, number, number]; // MuJoCo WXYZ
export type AssetId =
  | "cup"
  | "plate"
  | "spoon"
  | "cube"
  | "mesh"
  | "kalas_bowl"
  | "kalas_cup"
  | "kalas_spoon"
  | "kalas_plate";
export interface SceneObject {
  id: string;
  name: string;
  asset: AssetId;
  mesh?: { vertices: number[]; faces: number[]; filename: string } | null;
  position: Vec3;
  quaternion: Quat;
  scale: number;
  mass: number;
  friction: Vec3;
  collision: boolean;
  color: string;
}
export interface Table {
  width: number;
  depth: number;
  height: number;
}
export interface Scene {
  version: 1;
  name: string;
  table: Table;
  robot: { model: "so101"; position: Vec3; quaternion: Quat; joints: number[] };
  objects: SceneObject[];
  task: { source: string | null; target: string | null };
  cameras: Record<"main" | "top" | "front", CameraState>;
}
export interface Asset {
  id: AssetId;
  name: string;
  category: string;
  dimensions: Vec3;
  mass: number;
  color: string;
  description: string;
  approximate?: boolean;
  article?: string;
}
export interface Pose {
  id: number;
  position: Vec3;
  quaternion: Quat;
}
export interface ObjectPose {
  id: string;
  position: Vec3;
  quaternion: Quat;
}
export interface Geometry {
  id: number;
  name: string;
  owner: string;
  kind:
    "mesh" | "box" | "cylinder" | "capsule" | "sphere" | "ellipsoid" | "plane";
  size: Vec3;
  color: Quat;
  mesh: number;
}
export interface JointInfo {
  name: string;
  min: number;
  max: number;
}
export interface PathPlan {
  id?: string;
  status: "idle" | "calculating" | "ready" | "failed";
  points: Vec3[];
  duration: number;
  message: string;
  verified: boolean;
}
export interface TaskExample {
  id: string;
  name: string;
  description: string;
}
export interface StatePacket {
  plan?: PathPlan;
  type: "state" | "snapshot";
  revision: number;
  running: boolean;
  time: number;
  contacts: number;
  poses: Pose[];
  joints: number[];
  objects: ObjectPose[];
  requestId?: string;
  sessionId: string;
  sequence: number;
  mode: "policy" | "physics";
  task: {
    status: "idle" | "running" | "cancelled" | "succeeded" | "failed";
    phase: string;
    message: string;
    progress: number;
    success: boolean;
    graspAssist: boolean;
    held: boolean;
  };
  cameras: { wrist: { position: Vec3; quaternion: Quat; fov: number } };
}
export interface Snapshot extends StatePacket {
  type: "snapshot";
  scene: Scene;
  geometry: Geometry[];
  meshes?: MeshData;
  jointInfo: JointInfo[];
}
export interface CameraState {
  position: Vec3;
  target: Vec3;
  zoom: number;
  fov?: number;
}
export type ViewKind = "main" | "top" | "front" | "wrist";
export type Cameras = Record<ViewKind, CameraState>;
export interface SavedDocument {
  version: 1;
  scene: Scene;
  cameras?: Cameras;
}
export type MeshData = Record<string, { vertices: number[]; faces: number[] }>;
