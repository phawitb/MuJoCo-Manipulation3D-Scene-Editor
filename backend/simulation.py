"""Authoritative MuJoCo sessions and render packets from compiled geometry."""

from pathlib import Path
import math
import xml.etree.ElementTree as ET
from functools import lru_cache
import mujoco
import numpy as np
from .schema import Scene
from .catalog import KALAS, visual_mesh, collision_shapes

MODEL_DIR = Path(__file__).resolve().parents[1] / "assets" / "so101"
KINDS = {
    int(getattr(mujoco.mjtGeom, "mjGEOM_" + k.upper())): k
    for k in ("plane", "sphere", "capsule", "ellipsoid", "cylinder", "box", "mesh")
}


def numbers(values):
    return " ".join(str(float(v)) for v in values)


def add_object(world, obj):
    body = ET.SubElement(
        world,
        "body",
        name=f"object_{obj.id}",
        pos=numbers(obj.position),
        quat=numbers(obj.quaternion),
    )
    ET.SubElement(body, "freejoint")
    s = obj.scale
    shapes = []

    def shape(kind, size, pos=(0, 0, 0), **kw):
        shapes.append(
            dict(
                type=kind,
                size=numbers([v * s for v in size]),
                pos=numbers([v * s for v in pos]),
                **kw,
            )
        )

    if obj.asset in KALAS:
        shapes.append(
            dict(
                type="mesh",
                mesh=f"catalog_{obj.id}",
                group="2",
                contype="0",
                conaffinity="0",
                mass="0",
            )
        )
        for kind, size, pos, kw in collision_shapes(obj.asset):
            shape(kind, size, pos, group="3", **kw)
    elif obj.asset == "mesh":
        shapes.append(dict(type="mesh", mesh=f"imported_{obj.id}"))
    elif obj.asset == "cup":
        shape("cylinder", [0.033, 0.002], [0, 0, -0.048])
        for i in range(20):
            a = 2 * math.pi * i / 20
            shape(
                "box",
                [0.002, 0.0055, 0.048],
                [0.034 * math.cos(a), 0.034 * math.sin(a), 0.002],
                euler=numbers([0, 0, a]),
            )
    elif obj.asset == "plate":
        shape("cylinder", [0.068, 0.002], [0, 0, -0.004])
        for i in range(24):
            a = 2 * math.pi * i / 24
            shape(
                "box",
                [0.002, 0.009, 0.004],
                [0.068 * math.cos(a), 0.068 * math.sin(a), 0.002],
                euler=numbers([0, 0, a]),
            )
    elif obj.asset == "spoon":
        shape(
            "capsule",
            [0.003, 0.048],
            [-0.024, 0, 0],
            euler=numbers([0, math.pi / 2, 0]),
        )
        shape("ellipsoid", [0.025, 0.016, 0.004], [0.05, 0, 0])
    else:
        shape("box", [0.02, 0.02, 0.02])
    color = [int(obj.color[i : i + 2], 16) / 255 for i in (1, 3, 5)] + [1]
    for i, props in enumerate(shapes):
        attrs = dict(
            name=f"obj_{obj.id}_{i}",
            mass=str(obj.mass / sum(1 for shape in shapes if shape.get("mass") != "0")),
            rgba=numbers(color),
            friction=numbers(obj.friction),
            contype=str(int(obj.collision)),
            conaffinity=str(int(obj.collision)),
            solref="0.004 1",
            condim="6",
        )
        attrs.update(props)
        ET.SubElement(body, "geom", **attrs)


def build_xml(scene):
    root = ET.parse(MODEL_DIR / "so101.xml").getroot()
    root.find("compiler").set("meshdir", str(MODEL_DIR / "assets"))
    root.find("option").set("timestep", "0.001")
    root.find("option").set("iterations", "50")
    world = root.find("worldbody")
    base = world.find("body[@name='base']")
    base_position = list(scene.robot.position)
    base_position[2] += scene.robot.pedestal_height
    base.set("pos", numbers(base_position))
    base.set("quat", numbers(scene.robot.quaternion))
    t = scene.table
    ET.SubElement(
        world,
        "geom",
        name="floor",
        type="plane",
        size="3 3 .01",
        rgba=".075 .09 .11 1",
        friction=".8 .005 .0001",
    )
    ET.SubElement(
        world,
        "geom",
        name="table",
        type="box",
        pos=numbers([0, 0, t.height - 0.018]),
        size=numbers([t.width / 2, t.depth / 2, 0.018]),
        rgba=numbers([int(t.color[i : i + 2], 16) / 255 for i in (1, 3, 5)] + [1]),
        friction=".8 .005 .0001",
    )
    if scene.robot.pedestal_height > 0:
        # Support reaches the CAD base foot (2.4 mm below its link origin).
        # Keep this fixture in world coordinates so it also blocks arm contacts.
        top = base_position[2] - 0.0024
        bottom = min(t.height, top - scene.robot.pedestal_height)
        ET.SubElement(
            world,
            "geom",
            name="robot_pedestal",
            type="box",
            pos=numbers(
                [base_position[0] + 0.021, base_position[1], (top + bottom) / 2]
            ),
            size=numbers([0.055, 0.065, (top - bottom) / 2]),
            rgba=".25 .32 .35 1",
            friction=".8 .005 .0001",
        )
    for x in (-1, 1):
        for y in (-1, 1):
            ET.SubElement(
                world,
                "geom",
                name=f"leg_{x}_{y}",
                type="box",
                pos=numbers(
                    [
                        x * (t.width / 2 - 0.045),
                        y * (t.depth / 2 - 0.045),
                        (t.height - 0.036) / 2,
                    ]
                ),
                size=numbers([0.016, 0.016, (t.height - 0.036) / 2]),
                rgba=".18 .22 .25 1",
            )
    # Resolve the millimetre-scale utensil/jaw contacts without soft overlap.
    for cls in ("collision_gripper", "collision_gripper_mesh"):
        root.find(f".//default[@class='{cls}']/geom").set("solref", "0.004 1")
    # Gentle closing effort, below the source servo's 2.94 Nm stall limit.
    root.find("actuator/position[@name='gripper']").set("forcerange", "-0.5 0.5")
    for obj in scene.objects:
        if obj.asset in KALAS:
            vertices, faces = visual_mesh(obj.asset)
            ET.SubElement(
                root.find("asset"),
                "mesh",
                name=f"catalog_{obj.id}",
                vertex=numbers(vertices.reshape(-1) * obj.scale),
                face=" ".join(str(int(i)) for i in faces.reshape(-1)),
            )
        if obj.mesh:
            ET.SubElement(
                root.find("asset"),
                "mesh",
                name=f"imported_{obj.id}",
                vertex=numbers([x * obj.scale for x in obj.mesh.vertices]),
                face=" ".join(str(x) for x in obj.mesh.faces),
            )
        add_object(world, obj)
    return ET.tostring(root, encoding="unicode")


# Robot assets are immutable; compile the base once and use its compiled meshes.
@lru_cache(maxsize=1)
def compiled_meshes():
    model = mujoco.MjModel.from_xml_string(build_xml(Scene()))
    out = {}
    for i in range(model.nmesh):
        va, vn = model.mesh_vertadr[i], model.mesh_vertnum[i]
        fa, fn = model.mesh_faceadr[i], model.mesh_facenum[i]
        out[str(i)] = dict(
            vertices=model.mesh_vert[va : va + vn].reshape(-1).tolist(),
            faces=model.mesh_face[fa : fa + fn].reshape(-1).tolist(),
        )
    return out


class Simulation:
    def __init__(self, scene=None):
        self.running = False
        self.revision = 0
        self.load(scene or Scene())

    def load(self, scene):
        """Compile before swapping live state; a failed edit never destroys work."""
        scene = Scene.model_validate(scene.model_dump())
        model = mujoco.MjModel.from_xml_string(build_xml(scene))
        for field in ("joints", "reset_joints"):
            for i, value in enumerate(getattr(scene.robot, field)):
                lo, hi = model.jnt_range[i]
                if not math.isfinite(value) or not lo <= value <= hi:
                    raise ValueError(
                        f"{field}: {model.joint(i).name} must be between {lo:.3f} and {hi:.3f} rad"
                    )
        data = mujoco.MjData(model)
        data.qpos[:6] = scene.robot.joints
        data.ctrl[:] = scene.robot.joints
        mujoco.mj_forward(model, data)
        self.scene, self.model, self.data = scene.model_copy(deep=True), model, data
        self.running = False
        self.revision += 1
        self.object_bodies = {
            o.id: model.body(f"object_{o.id}").id for o in scene.objects
        }
        from .policy import PickPlacePolicy

        self.policy = PickPlacePolicy(self)
        self.visible_ids = [
            i for i in range(model.ngeom) if model.geom_group[i] not in (3, 4)
        ]

    def step(self, count=1):
        # A physics result must remain valid input for saving, editing and recovery.
        state_type = mujoco.mjtState.mjSTATE_INTEGRATION
        previous = np.empty(mujoco.mj_stateSize(self.model, state_type))
        mujoco.mj_getState(self.model, self.data, previous, state_type)
        for _ in range(count):
            active = self.policy.status == "running"
            self.policy.update()
            mujoco.mj_step(self.model, self.data)
            mujoco.mj_forward(self.model, self.data)
            if active:
                from .safety import collision_issue, joint_issue

                issue = collision_issue(self) or joint_issue(self)
                if issue:
                    self.policy.fail(
                        issue + " Motion stopped; adjust the scene and calculate again."
                    )
                # Pause at the exact terminal state that was checked, rather
                # than executing unchecked substeps left in the UI batch.
                if not self.running:
                    break
        mujoco.mj_forward(self.model, self.data)
        escaped = not np.isfinite(self.data.qpos).all() or any(
            np.any(np.abs(self.data.xpos[bid]) > 5)
            for bid in self.object_bodies.values()
        )
        if escaped:
            mujoco.mj_setState(self.model, self.data, previous, state_type)
            mujoco.mj_forward(self.model, self.data)
            self.running = False
            raise ValueError(
                "Object reached the 5 m workspace boundary. Physics paused at the last valid state; enable collision, reposition the object, or reset."
            )

    def start_policy(self):
        self.policy.start()
        self.running = True

    def stop_policy(self):
        self.policy.cancel()
        self.running = False

    def export_scene(self):
        scene = self.scene.model_copy(deep=True)
        for obj in scene.objects:
            bid = self.object_bodies[obj.id]
            obj.position = self.data.xpos[bid].tolist()
            obj.quaternion = self.data.xquat[bid].tolist()
        scene.robot.joints = np.clip(
            self.data.qpos[:6], self.model.jnt_range[:6, 0], self.model.jnt_range[:6, 1]
        ).tolist()
        return scene

    def state(self):
        poses = []
        quat = np.zeros(4)
        for i in self.visible_ids:
            mujoco.mju_mat2Quat(quat, self.data.geom_xmat[i])
            poses.append(
                dict(
                    id=i,
                    position=self.data.geom_xpos[i].tolist(),
                    quaternion=quat.tolist(),
                )
            )
        return dict(
            type="state",
            revision=self.revision,
            running=self.running,
            time=float(self.data.time),
            timeStep=float(self.model.opt.timestep),
            contacts=int(self.data.ncon),
            task=self.policy.packet(),
            cameras=self.camera_poses(),
            poses=poses,
            joints=self.data.qpos[:6].tolist(),
            objects=[
                dict(
                    id=o.id,
                    position=self.data.xpos[self.object_bodies[o.id]].tolist(),
                    quaternion=self.data.xquat[self.object_bodies[o.id]].tolist(),
                )
                for o in self.scene.objects
            ],
        )

    def camera_poses(self):
        camera = self.data.camera("wrist_cam")
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, camera.xmat)
        return {
            "wrist": dict(
                position=camera.xpos.tolist(),
                quaternion=q.tolist(),
                fov=float(self.model.cam_fovy[self.model.camera("wrist_cam").id]),
            )
        }

    def geometry(self):
        out = []
        reverse = {v: k for k, v in self.object_bodies.items()}
        for i in self.visible_ids:
            body = int(self.model.geom_bodyid[i])
            name = self.model.geom(i).name or f"geom_{i}"
            owner = reverse.get(
                body,
                "robot"
                if body or name == "robot_pedestal"
                else ("floor" if name == "floor" else "table"),
            )
            color = self.model.geom_rgba[i].copy()
            material = self.model.geom_matid[i]
            if material >= 0:
                color = self.model.mat_rgba[material]
            out.append(
                dict(
                    id=i,
                    name=name,
                    owner=owner,
                    kind=KINDS[int(self.model.geom_type[i])],
                    size=self.model.geom_size[i].tolist(),
                    color=color.tolist(),
                    mesh=int(self.model.geom_dataid[i]),
                )
            )
        return out

    def snapshot(self):
        return dict(
            **{**self.state(), "type": "snapshot"},
            scene=self.export_scene().model_dump(),
            geometry=self.geometry(),
            meshes=self.imported_meshes(),
            jointInfo=[
                dict(
                    name=self.model.joint(i).name,
                    min=float(self.model.jnt_range[i, 0]),
                    max=float(self.model.jnt_range[i, 1]),
                )
                for i in range(6)
            ],
        )

    def imported_meshes(self):
        out = {}
        for i in range(self.model.nmesh):
            if not (self.model.mesh(i).name or "").startswith(
                ("imported_", "catalog_")
            ):
                continue
            va, vn = self.model.mesh_vertadr[i], self.model.mesh_vertnum[i]
            fa, fn = self.model.mesh_faceadr[i], self.model.mesh_facenum[i]
            out[str(i)] = dict(
                vertices=self.model.mesh_vert[va : va + vn].reshape(-1).tolist(),
                faces=self.model.mesh_face[fa : fa + fn].reshape(-1).tolist(),
            )
        return out

    def meshes(self):
        return compiled_meshes()
