import { useEffect, useMemo, useRef, useState } from "react";
import type { MutableRefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, TransformControls } from "@react-three/drei";
import {
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  CapsuleGeometry,
  CylinderGeometry,
  Group,
  Matrix4,
  Mesh,
  Plane,
  PlaneGeometry,
  Quaternion,
  Raycaster,
  SphereGeometry,
  Vector2,
  Vector3,
  MOUSE,
  PerspectiveCamera,
} from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { Focus, RotateCcw, Maximize2, Settings2 } from "lucide-react";
import type {
  Asset,
  CameraState,
  Geometry,
  MeshData,
  ObjectPose,
  Quat,
  Snapshot,
  StatePacket,
  Vec3,
  ViewKind,
} from "./types";
import { PlacementGhost, SelectionHalo, GripperPath } from "./SceneOverlays";
import {
  dropPosition,
  defaultCameras,
  toMujocoQuaternion,
  toThreeQuaternion,
} from "./math";

import type { PlacementCursor } from "./Library";

interface Props {
  kind: ViewKind;
  renderEnabled?: boolean;
  assets: Asset[];
  dragAsset: Asset | null;
  dragCursor: PlacementCursor | null;
  highlight: { id: string; token: number } | null;
  path: Vec3[];
  snapshot: Snapshot;
  live: MutableRefObject<StatePacket | null>;
  meshes: MeshData;
  selected: string | null;
  select: (id: string | null) => void;
  editable: boolean;
  transform: "translate" | "rotate";
  snap: boolean;
  onTransform: (id: string, position: Vec3, quaternion: Quat) => void;
  onDrop: (asset: string, point: Vec3) => void;
  cameraState: CameraState;
  saveCamera: (kind: ViewKind, state: CameraState, remember?: boolean) => void;
  frameSignal: number;
  resetSignal: number;
  active: boolean;
  onActive: () => void;
  grid: boolean;
  cameraEpoch: number;
  preview: MutableRefObject<ObjectPose | null>;
  onExpand?: () => void;
  editCamera?: (kind: ViewKind) => void;
  picking?: boolean;
}
function makeGeometry(g: Geometry, meshes: MeshData) {
  const [x, y, z] = g.size;
  let geometry: BufferGeometry;
  switch (g.kind) {
    case "mesh": {
      const raw = meshes[String(g.mesh)];
      geometry = new BufferGeometry();
      if (raw) {
        geometry.setAttribute(
          "position",
          new BufferAttribute(new Float32Array(raw.vertices), 3),
        );
        geometry.setIndex(raw.faces);
        geometry.computeVertexNormals();
      }
      break;
    }
    case "box":
      geometry = new BoxGeometry(x * 2, y * 2, z * 2);
      break;
    case "cylinder":
      geometry = new CylinderGeometry(x, x, y * 2, 40).rotateX(Math.PI / 2);
      break;
    case "capsule":
      geometry = new CapsuleGeometry(x, y * 2, 6, 16).rotateX(Math.PI / 2);
      break;
    case "sphere":
      geometry = new SphereGeometry(x, 24, 16);
      break;
    case "ellipsoid":
      geometry = new SphereGeometry(1, 32, 16).scale(x, y, z);
      break;
    default:
      geometry = new PlaneGeometry(200, 200);
  }
  return geometry;
}
function SimGeom({
  geom,
  meshes,
  live,
  selected,
  select,
  preview,
}: Pick<Props, "meshes" | "live" | "selected" | "select" | "preview"> & {
  geom: Geometry;
}) {
  const ref = useRef<Mesh>(null);
  const geometry = useMemo(() => makeGeometry(geom, meshes), [geom, meshes]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  const scratch = useMemo(
    () => ({
      m: new Matrix4(),
      old: new Matrix4(),
      next: new Matrix4(),
      scale: new Vector3(1, 1, 1),
      pos: new Vector3(),
      q: new Quaternion(),
    }),
    [],
  );
  useFrame(() => {
    const pose = live.current?.poses.find((p) => p.id === geom.id);
    if (!pose || !ref.current) return;
    ref.current.position.fromArray(pose.position);
    ref.current.quaternion.copy(toThreeQuaternion(pose.quaternion));
    const p = preview.current;
    if (p?.id === geom.owner) {
      const origin = live.current?.objects.find((o) => o.id === p.id);
      if (origin) {
        scratch.old
          .compose(
            scratch.pos.fromArray(origin.position),
            toThreeQuaternion(origin.quaternion),
            scratch.scale,
          )
          .invert();
        scratch.next.compose(
          scratch.pos.fromArray(p.position),
          toThreeQuaternion(p.quaternion),
          scratch.scale,
        );
        scratch.m
          .compose(ref.current.position, ref.current.quaternion, scratch.scale)
          .premultiply(scratch.old)
          .premultiply(scratch.next);
        scratch.m.decompose(
          ref.current.position,
          ref.current.quaternion,
          ref.current.scale,
        );
      }
    }
  });
  const color = `rgb(${geom.color
    .slice(0, 3)
    .map((c) => Math.round(c * 255))
    .join(",")})`;
  return (
    <mesh
      ref={ref}
      geometry={geometry}
      castShadow={geom.owner !== "floor"}
      receiveShadow
      onClick={(e) => {
        e.stopPropagation();
        select(
          geom.owner === "floor" || geom.owner === "table" ? null : geom.owner,
        );
      }}
    >
      <meshStandardMaterial
        color={color}
        roughness={
          geom.owner === "floor" ? 1 : geom.owner === "table" ? 0.9 : 0.65
        }
        metalness={geom.owner === "robot" ? 0.12 : 0}
        emissive={selected === geom.owner ? "#28574e" : "#000000"}
        emissiveIntensity={0.24}
      />
    </mesh>
  );
}
function SelectionGizmo(p: Props) {
  const pivot = useRef<Group>(null);
  const dragging = useRef(false);
  const selected = p.snapshot.scene.objects.find((o) => o.id === p.selected);
  const pos = selected?.position || [0, 0, 0];
  useFrame(() => {
    if (!pivot.current || dragging.current || !selected) return;
    const pose =
      p.preview.current?.id === selected.id
        ? p.preview.current
        : p.live.current?.objects.find((o) => o.id === selected.id);
    if (pose) {
      pivot.current.position.fromArray(pose.position);
      pivot.current.quaternion.copy(toThreeQuaternion(pose.quaternion));
    }
  });
  useEffect(
    () => () => {
      p.preview.current = null;
    },
    [selected?.id, p.preview],
  );
  if (!selected) return null;
  return (
    <>
      <group ref={pivot} position={pos as Vec3} />
      {p.editable && p.active && !p.picking && p.kind !== "wrist" && (
        <TransformControls
          object={pivot as React.RefObject<Group>}
          mode={p.transform}
          space="world"
          size={0.8}
          translationSnap={p.snap ? 0.01 : null}
          rotationSnap={p.snap ? Math.PI / 12 : null}
          onMouseDown={() => {
            dragging.current = true;
          }}
          onObjectChange={() => {
            if (dragging.current && pivot.current)
              p.preview.current = {
                id: selected.id,
                position: pivot.current.position.toArray() as Vec3,
                quaternion: toMujocoQuaternion(pivot.current.quaternion),
              };
          }}
          onMouseUp={() => {
            if (pivot.current) {
              const position = pivot.current.position.toArray() as Vec3;
              const q = toMujocoQuaternion(pivot.current.quaternion);
              p.onTransform(selected.id, position, q);
            }
            dragging.current = false;
            p.preview.current = null;
          }}
        />
      )}
    </>
  );
}
function CameraRig(
  p: Props & {
    dropRef: MutableRefObject<((x: number, y: number) => Vec3 | null) | null>;
  },
) {
  const { camera, gl } = useThree();
  const controls = useRef<OrbitControlsImpl>(null);
  const initial = useRef(p.cameraState);
  const target = useRef(new Vector3(...p.cameraState.target));
  const consumedFrame = useRef(p.frameSignal);
  const consumedReset = useRef(p.resetSignal);
  const stateRef = useRef(p);
  stateRef.current = p;
  const apply = (state: CameraState) => {
    camera.position.fromArray(state.position);
    camera.up.set(p.kind === "top" ? 1 : 0, 0, p.kind === "top" ? 0 : 1);
    target.current.fromArray(state.target);
    camera.lookAt(target.current);
    camera.zoom = state.zoom;
    if (camera instanceof PerspectiveCamera) camera.fov = state.fov || 42;
    camera.updateProjectionMatrix();
    controls.current?.target.fromArray(state.target);
    controls.current?.update();
  };
  const save = (remember = false) => {
    p.saveCamera(
      p.kind,
      {
        position: camera.position.toArray() as Vec3,
        target: (controls.current?.target || target.current).toArray() as Vec3,
        zoom: camera.zoom,
        fov: (camera as PerspectiveCamera).fov || 50,
      },
      remember,
    );
  };
  useFrame(() => {
    if (p.kind !== "wrist") return;
    const wrist = p.live.current?.cameras?.wrist;
    if (!wrist) return;
    camera.position.fromArray(wrist.position);
    camera.quaternion.copy(toThreeQuaternion(wrist.quaternion));
    if (camera instanceof PerspectiveCamera && camera.fov !== wrist.fov) {
      camera.fov = wrist.fov;
      camera.updateProjectionMatrix();
    }
  });
  useEffect(() => {
    apply(initial.current);
  }, []);
  useEffect(() => {
    const changed = consumedReset.current !== p.resetSignal;
    consumedReset.current = p.resetSignal;
    if (changed && p.active) {
      apply(defaultCameras()[p.kind]);
      save(p.kind !== "top");
    }
  }, [p.resetSignal]);
  useEffect(() => {
    const changed = consumedFrame.current !== p.frameSignal;
    consumedFrame.current = p.frameSignal;
    if (!changed || !p.active || p.kind !== "main" || !controls.current) return;
    let target: Vec3 = [0, 0, p.snapshot.scene.table.height];
    if (p.selected === "robot")
      target = p.snapshot.scene.robot.position.map(
        (v, i) => v + (i === 2 ? 0.15 : 0),
      ) as Vec3;
    else {
      const obj = p.live.current?.objects.find((o) => o.id === p.selected);
      if (obj) target = obj.position;
    }
    const delta = new Vector3().subVectors(
      camera.position,
      controls.current.target,
    );
    const objectSelected = p.snapshot.scene.objects.some(
      (o) => o.id === p.selected,
    );
    delta.setLength(objectSelected ? 0.35 : 1.25);
    camera.position.copy(new Vector3(...target).add(delta));
    controls.current.target.fromArray(target);
    camera.updateProjectionMatrix();
    controls.current.update();
    save();
  }, [p.frameSignal]);
  useEffect(() => {
    p.dropRef.current = (x, y) => {
      const bounds = gl.domElement.getBoundingClientRect();
      const ray = new Raycaster();
      ray.setFromCamera(
        new Vector2(
          ((x - bounds.left) / bounds.width) * 2 - 1,
          (-(y - bounds.top) / bounds.height) * 2 + 1,
        ),
        camera,
      );
      const point = new Vector3();
      const hit = ray.ray.intersectPlane(
        new Plane(
          new Vector3(0, 0, 1),
          -stateRef.current.snapshot.scene.table.height,
        ),
        point,
      );
      if (!hit) return null;
      const table = stateRef.current.snapshot.scene.table;
      if (
        Math.abs(point.x) > table.width / 2 + 0.04 ||
        Math.abs(point.y) > table.depth / 2 + 0.04
      )
        return null;
      return point.toArray() as Vec3;
    };
    return () => {
      p.dropRef.current = null;
    };
  }, [camera, gl]);
  if (p.kind !== "main" && p.kind !== "top") return null;
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.12}
      enableRotate={p.kind === "main"}
      enablePan={p.kind === "main"}
      enableZoom
      minDistance={0.12}
      maxDistance={5}
      minZoom={100}
      maxZoom={2500}
      minPolarAngle={p.kind === "top" ? Math.PI / 2 : 0}
      maxPolarAngle={p.kind === "top" ? Math.PI / 2 : Math.PI * 0.49}
      mouseButtons={{
        LEFT: p.kind === "top" ? MOUSE.PAN : MOUSE.ROTATE,
        MIDDLE: MOUSE.DOLLY,
        RIGHT: MOUSE.PAN,
      }}
      onEnd={() => save()}
    />
  );
}
function TableGrid({
  width,
  depth,
  height,
}: {
  width: number;
  depth: number;
  height: number;
}) {
  const geometry = useMemo(() => {
    const vertices: number[] = [];
    for (let x = -width / 2; x <= width / 2 + 0.00001; x += 0.05)
      vertices.push(
        x,
        -depth / 2,
        height + 0.0006,
        x,
        depth / 2,
        height + 0.0006,
      );
    for (let y = -depth / 2; y <= depth / 2 + 0.00001; y += 0.05)
      vertices.push(
        -width / 2,
        y,
        height + 0.0006,
        width / 2,
        y,
        height + 0.0006,
      );
    return new BufferGeometry().setAttribute(
      "position",
      new BufferAttribute(new Float32Array(vertices), 3),
    );
  }, [width, depth, height]);
  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color="#254a50" transparent opacity={0.2} />
    </lineSegments>
  );
}
function Contents(
  p: Props & {
    dropRef: MutableRefObject<((x: number, y: number) => Vec3 | null) | null>;
    ghost: Vec3 | null;
  },
) {
  const highlighted = p.snapshot.scene.objects.find(
    (o) => o.id === p.highlight?.id,
  );
  return (
    <>
      <color attach="background" args={["#202a30"]} />
      <fog attach="fog" args={["#202a30", 2.4, 5]} />
      <ambientLight intensity={1.3} />
      <hemisphereLight args={["#dae8f1", "#495559", 1.3]} />
      <directionalLight
        position={[1, -1, 3]}
        intensity={2.5}
        castShadow
        shadow-mapSize={p.kind === "main" ? [1024, 1024] : [512, 512]}
        shadow-camera-left={-1}
        shadow-camera-right={1}
        shadow-camera-top={1}
        shadow-camera-bottom={-1}
        shadow-bias={-0.0003}
      />
      <directionalLight position={[-2, 2, 1.5]} intensity={1} />
      {p.snapshot.geometry.map((g) => (
        <SimGeom
          key={`${p.snapshot.revision}-${g.id}`}
          geom={g}
          meshes={p.meshes}
          live={p.live}
          selected={p.selected}
          select={p.select}
          preview={p.preview}
        />
      ))}
      {p.grid && (
        <>
          <gridHelper
            args={[3, 60, "#4c626a", "#34454b"]}
            rotation={[Math.PI / 2, 0, 0]}
            position={[0, 0, 0.002]}
          >
            <lineBasicMaterial color="#76949b" transparent opacity={0.13} />
          </gridHelper>
          <TableGrid {...p.snapshot.scene.table} />
        </>
      )}
      <axesHelper
        args={[0.09]}
        position={[
          p.snapshot.scene.table.width / 2 + 0.025,
          -p.snapshot.scene.table.depth / 2,
          p.snapshot.scene.table.height,
        ]}
      />
      {p.dragAsset && p.ghost && (
        <PlacementGhost asset={p.dragAsset} position={p.ghost} />
      )}
      {highlighted && (
        <SelectionHalo
          key={p.highlight?.token}
          object={highlighted}
          assets={p.assets}
          live={p.live}
        />
      )}
      <GripperPath points={p.path} />
      <CameraRig {...p} />
      <SelectionGizmo {...p} />
    </>
  );
}
export function Viewport(p: Props) {
  const dropRef = useRef<(x: number, y: number) => Vec3 | null>(null);
  const pointerStart = useRef<[number, number]>([0, 0]);
  const [dragOver, setDragOver] = useState(false);
  const [ghost, setGhost] = useState<Vec3 | null>(null);
  useEffect(() => {
    if (!p.dragAsset) {
      setGhost(null);
      setDragOver(false);
    }
  }, [p.dragAsset]);
  const section = useRef<HTMLElement>(null);
  const committed = useRef<PlacementCursor | null>(null);
  useEffect(() => {
    const cursor = p.dragCursor;
    const rect = section.current?.getBoundingClientRect();
    const inside =
      cursor &&
      rect &&
      rect.width > 0 &&
      rect.height > 0 &&
      cursor.x >= rect.left &&
      cursor.x < rect.right &&
      cursor.y >= rect.top &&
      cursor.y < rect.bottom;
    const overControl =
      cursor &&
      document
        .elementFromPoint(cursor.x, cursor.y)
        ?.closest("button, input, select, textarea, [role=dialog]");
    const hit =
      inside && !overControl && p.editable && p.dragAsset
        ? dropRef.current?.(cursor.x, cursor.y)
        : null;
    if (!cursor || !p.dragAsset || !hit) {
      setGhost(null);
      setDragOver(false);
      return;
    }
    if (cursor.drop) {
      setGhost(null);
      setDragOver(false);
      if (committed.current !== cursor) {
        committed.current = cursor;
        p.onActive();
        p.onDrop(p.dragAsset.id, hit);
      }
    } else {
      try {
        setGhost(
          dropPosition(hit, p.dragAsset.dimensions, p.snapshot.scene.table),
        );
        setDragOver(true);
      } catch {
        setGhost(null);
        setDragOver(false);
      }
    }
  }, [p.dragCursor, p.dragAsset, p.editable]);
  const [localFrame, setLocalFrame] = useState(0),
    [localReset, setLocalReset] = useState(0);
  return (
    <section
      ref={section}
      data-testid={`viewport-${p.kind}`}
      data-highlight={p.highlight?.id || ""}
      data-path-visible={p.path.length > 1 ? "true" : "false"}
      data-preview-position={ghost ? JSON.stringify(ghost) : ""}
      className={`viewport ${p.active ? "active" : ""} ${dragOver ? "drop-target" : ""}`}
      onPointerDown={p.onActive}
      onPointerDownCapture={(e) => {
        pointerStart.current = [e.clientX, e.clientY];
      }}
      onClickCapture={(e) => {
        if (
          Math.hypot(
            e.clientX - pointerStart.current[0],
            e.clientY - pointerStart.current[1],
          ) > 4
        )
          e.stopPropagation();
      }}
    >
      <div className="viewport-heading">
        <span className="view-dot" />
        <strong>
          {
            {
              main: "Main 3D View",
              top: "Top View",
              front: "Front Camera",
              back: "Back Camera",
              wrist: "Wrist Camera",
            }[p.kind]
          }
        </strong>
        <span className="view-projection">
          {p.kind === "top"
            ? "ORTHOGRAPHIC"
            : p.kind === "wrist"
              ? "LIVE · ARM"
              : "PERSPECTIVE"}
        </span>
        <div className="view-actions">
          {(p.kind === "main" || p.kind === "front" || p.kind === "back") && (
            <button
              title="Edit camera position"
              aria-label={`Edit ${p.kind} camera`}
              onClick={() => p.editCamera?.(p.kind)}
            >
              <Settings2 size={14} />
            </button>
          )}
          {(p.kind === "main" || p.kind === "top") && (
            <>
              {p.kind === "main" && (
                <button
                  title="Frame selected"
                  aria-label={`Frame ${p.kind} camera`}
                  onClick={() => {
                    p.onActive();
                    setLocalFrame((x) => x + 1);
                  }}
                >
                  <Focus size={14} />
                </button>
              )}
              <button
                title="Reset camera"
                aria-label={`Reset ${p.kind} camera`}
                onClick={() => {
                  p.onActive();
                  setLocalReset((x) => x + 1);
                }}
              >
                <RotateCcw size={13} />
              </button>
            </>
          )}
          {p.onExpand && (
            <button
              title="Toggle expanded view"
              aria-label={`Expand ${p.kind} view`}
              onClick={p.onExpand}
            >
              <Maximize2 size={13} />
            </button>
          )}
        </div>
      </div>
      <Canvas
        frameloop={p.renderEnabled === false ? "never" : "always"}
        key={`${p.kind}-${p.cameraEpoch}`}
        shadows
        dpr={[1, 1.5]}
        orthographic={p.kind === "top"}
        camera={{
          position: p.cameraState.position,
          up: p.kind === "top" ? [1, 0, 0] : [0, 0, 1],
          near: 0.005,
          far: 20,
          fov: p.cameraState.fov || 42,
          zoom: p.cameraState.zoom,
        }}
        onPointerMissed={() => p.select(null)}
      >
        <Contents
          {...p}
          frameSignal={p.frameSignal + localFrame * 10000}
          resetSignal={p.resetSignal + localReset * 10000}
          dropRef={dropRef}
          ghost={ghost}
        />
      </Canvas>
      <div className="viewport-caption">
        {p.kind === "wrist"
          ? "Mounted on wrist · follows the arm"
          : p.kind === "top"
            ? "Scroll to zoom · Robot side below"
            : p.kind === "main"
              ? "Drag to orbit · Right-drag to pan · Scroll to zoom"
              : "Fixed view · Edit camera to change setup"}
        <span>m · Z ↑</span>
      </div>
    </section>
  );
}
