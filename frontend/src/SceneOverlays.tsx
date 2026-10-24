import { useMemo, useRef, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import { Color, Group, LatheGeometry, Vector2 } from "three";
import type { MutableRefObject } from "react";
import type { Asset, SceneObject, StatePacket, Vec3 } from "./types";
import { objectDimensions } from "./interaction";

export function PlacementGhost({
  asset,
  position,
  tableHeight,
}: {
  asset: Asset;
  position: Vec3;
  tableHeight: number;
}) {
  const [x, y, z] = asset.dimensions;
  const family = asset.id.replace("kalas_", "");
  const shell = useMemo(() => {
    const r = x / 2,
      h = z / 2,
      base = family === "plate" ? r * 0.82 : r * 0.76,
      t = 0.002;
    return new LatheGeometry(
      [
        [0, -h],
        [base, -h],
        [r, h],
        [r - t, h],
        [base - t, -h + t],
        [0, -h + t],
      ].map((p) => new Vector2(...(p as [number, number]))),
      48,
    ).rotateX(Math.PI / 2);
  }, [x, z, family]);
  useEffect(() => () => shell.dispose(), [shell]);
  const material = (
    <meshStandardMaterial
      color={asset.color}
      transparent
      opacity={0.35}
      depthWrite={false}
      roughness={0.5}
      emissive={asset.color}
      emissiveIntensity={0.3}
    />
  );
  return (
    <group raycast={() => {}}>
      <group position={position}>
        {(family === "cup" || family === "bowl" || family === "plate") && (
          <Line
            points={Array.from(
              { length: 65 },
              (_, i) =>
                [
                  (x / 2) * Math.cos((i * Math.PI) / 32),
                  (y / 2) * Math.sin((i * Math.PI) / 32),
                  z / 2,
                ] as Vec3,
            )}
            color="#73ffd0"
            lineWidth={2}
            transparent
            opacity={0.9}
          />
        )}

        {family === "cup" || family === "bowl" || family === "plate" ? (
          <mesh geometry={shell}>{material}</mesh>
        ) : family === "spoon" ? (
          <>
            <mesh position={[-x * 0.16, 0, 0]}>
              <boxGeometry args={[x * 0.67, y * 0.36, z * 0.4]} />
              {material}
            </mesh>
            <mesh position={[x * 0.33, 0, 0]} scale={[x * 0.17, y / 2, z / 2]}>
              <sphereGeometry args={[1, 24, 12]} />
              {material}
            </mesh>
          </>
        ) : (
          <mesh>
            <boxGeometry args={[x, y, z]} />
            {material}
          </mesh>
        )}
        <axesHelper args={[0.055]} />
      </group>
      <mesh position={[position[0], position[1], tableHeight + 0.001]}>
        <planeGeometry args={[x + 0.008, y + 0.008]} />
        <meshBasicMaterial
          color="#b2efd7"
          transparent
          opacity={0.18}
          depthWrite={false}
        />
      </mesh>
      <Line
        points={[
          [position[0] - x / 2, position[1] - y / 2, tableHeight + 0.002],
          [position[0] + x / 2, position[1] - y / 2, tableHeight + 0.002],
          [position[0] + x / 2, position[1] + y / 2, tableHeight + 0.002],
          [position[0] - x / 2, position[1] + y / 2, tableHeight + 0.002],
          [position[0] - x / 2, position[1] - y / 2, tableHeight + 0.002],
        ]}
        color="#b2efd7"
        lineWidth={1.5}
      />
    </group>
  );
}

export function SelectionHalo({
  object,
  assets,
  live,
}: {
  object: SceneObject;
  assets: Asset[];
  live: MutableRefObject<StatePacket | null>;
}) {
  const group = useRef<Group>(null);
  const dims = objectDimensions(object, assets),
    radius = Math.hypot(dims[0], dims[1]) / 2 + 0.008;
  const born = useRef(performance.now());
  useFrame(() => {
    if (!group.current) return;
    const pose = live.current?.objects.find((o) => o.id === object.id);
    if (pose)
      group.current.position.set(
        pose.position[0],
        pose.position[1],
        pose.position[2] - dims[2] / 2 + 0.004,
      );
    const pulse = 1 + 0.05 * Math.sin((performance.now() - born.current) / 140);
    group.current.scale.set(pulse, pulse, 1);
  });
  return (
    <group ref={group} raycast={() => {}}>
      <mesh>
        <ringGeometry args={[radius * 0.85, radius, 64]} />
        <meshBasicMaterial
          color="#e7f9a2"
          transparent
          opacity={0.8}
          depthWrite={false}
        />
      </mesh>
      <mesh>
        <ringGeometry args={[radius, radius * 1.25, 64]} />
        <meshBasicMaterial
          color="#9ce5c3"
          transparent
          opacity={0.17}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

export function GripperPath({ points }: { points: Vec3[] }) {
  const colors = useMemo(
    () =>
      points.map((_, i) =>
        new Color().setHSL(
          0.72 * (1 - i / Math.max(1, points.length - 1)),
          0.9,
          0.65,
        ),
      ),
    [points],
  );
  if (points.length < 2) return null;
  return (
    <group raycast={() => {}}>
      <Line
        points={points}
        vertexColors={colors}
        lineWidth={2.5}
        transparent
        opacity={0.88}
      />
      <mesh position={points[0]}>
        <sphereGeometry args={[0.004, 12, 8]} />
        <meshBasicMaterial color={colors[0]} />
      </mesh>
      <mesh position={points[points.length - 1]}>
        <sphereGeometry args={[0.004, 12, 8]} />
        <meshBasicMaterial color={colors[colors.length - 1]} />
      </mesh>
    </group>
  );
}
