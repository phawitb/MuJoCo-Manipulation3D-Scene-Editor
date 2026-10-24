export interface PortableObject {
  id: string;
  name: string;
  asset: "mesh";
  mesh: { vertices: number[]; faces: number[]; filename: string };
  position: [number, number, number];
  quaternion: [number, number, number, number];
  scale: number;
  mass: number;
  friction: [number, number, number];
  collision: boolean;
  color: string;
}
export interface ReconstructionResult {
  object: PortableObject;
  glb_base64: string;
  filename: string;
  metadata: {
    provider: string;
    mode: "extrude" | "revolve";
    dimensions_m: number[];
    vertices: number;
    triangles: number;
    watertight: boolean;
    volume_m3: number;
    source_pixels: number[];
    mask_png_base64: string;
    warnings: string[];
  };
}
export interface GymSession {
  sessionId: string;
  name: string;
  running: boolean;
  viewers: number;
}
