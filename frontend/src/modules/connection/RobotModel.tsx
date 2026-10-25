import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { LoadingManager, Mesh, type Material } from "three";
import URDFLoader, { type URDFRobot } from "urdf-loader";
import { type Telemetry } from "./api";
import { measuredRobotPose } from "./robotPose";

function disposeRobot(robot: URDFRobot) {
  const materials = new Set<Material>();
  robot.traverse((object) => {
    if (object instanceof Mesh) {
      object.geometry.dispose();
      (Array.isArray(object.material)
        ? object.material
        : [object.material]
      ).forEach((m) => materials.add(m));
    }
  });
  materials.forEach((m) => m.dispose());
}

function MeasuredArm({
  robot,
  pose,
}: {
  robot: URDFRobot;
  pose: Record<string, number>;
}) {
  const invalidate = useThree((state) => state.invalidate);
  useLayoutEffect(() => {
    robot.setJointValues(pose);
    invalidate();
  }, [robot, pose, invalidate]);
  return <primitive object={robot} dispose={null} />;
}

export default function RobotModel({ telemetry }: { telemetry: Telemetry[] }) {
  const [robot, setRobot] = useState<URDFRobot | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const pose = useMemo(() => measuredRobotPose(telemetry), [telemetry]);
  useEffect(() => {
    let active = true;
    let loaded: URDFRobot | null = null;
    let complete = false;
    let failed = false;
    setError(false);
    setRobot(null);
    const manager = new LoadingManager();
    const fail = () => {
      failed = true;
      if (active) setError(true);
    };
    manager.onError = fail;
    manager.onLoad = () => {
      complete = true;
      if (!loaded) return;
      if (!active || failed) disposeRobot(loaded);
      else setRobot(loaded);
    };
    const loader = new URDFLoader(manager);
    loader.parseCollision = false;
    loader.load(
      "/robots/so101/so101.urdf",
      (model) => {
        loaded = model;
        // Display the measured angle even if it is outside a configured limit.
        // Clamping the picture would hide a real encoder/limit discrepancy.
        Object.values(model.joints).forEach((joint) => {
          joint.ignoreLimits = true;
        });
      },
      undefined,
      fail,
    );
    return () => {
      active = false;
      if (complete && loaded && !failed) disposeRobot(loaded);
    };
  }, [attempt]);

  return (
    <div className="manual-model" aria-label="Live measured SO-101 URDF model">
      {error ? (
        <div className="manual-model-message" role="alert">
          <p>Could not load the SO-101 model.</p>
          <button onClick={() => setAttempt((n) => n + 1)}>Retry model</button>
        </div>
      ) : !robot || !pose ? (
        <p className="manual-model-message" role="status">
          {!robot
            ? "Loading SO-101 model…"
            : "Waiting for calibrated encoder feedback…"}
        </p>
      ) : (
        <Canvas
          frameloop="demand"
          camera={{
            position: [0.45, -0.55, 0.3],
            up: [0, 0, 1],
            fov: 40,
            near: 0.01,
            far: 10,
          }}
        >
          <ambientLight intensity={1.5} />
          <directionalLight position={[1, -1, 2]} intensity={2} />
          <directionalLight position={[-1, 1, 0.7]} intensity={1} />
          <MeasuredArm robot={robot} pose={pose} />
          <OrbitControls
            target={[0.07, 0, 0.08]}
            enablePan={false}
            minDistance={0.3}
            maxDistance={1.5}
          />
        </Canvas>
      )}
      <span>SO-101 · URDF · Encoder feedback</span>
    </div>
  );
}
