"""Authoritative MuJoCo sessions and render packets from compiled geometry."""

from pathlib import Path
import math
import xml.etree.ElementTree as ET
from functools import lru_cache
import mujoco
import numpy as np
from .schema import Scene

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

    if obj.asset == "cup":
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
        ET.SubElement(
            body,
            "geom",
            name=f"obj_{obj.id}_{i}",
            mass=str(obj.mass / len(shapes)),
            rgba=numbers(color),
            friction=numbers(obj.friction),
            contype=str(int(obj.collision)),
            conaffinity=str(int(obj.collision)),
            solref="0.01 1",
            condim="6",
            **props,
        )


def build_xml(scene):
    root = ET.parse(MODEL_DIR / "so101.xml").getroot()
    root.find("compiler").set("meshdir", str(MODEL_DIR / "assets"))
    root.find("option").set("timestep", "0.002")
    root.find("option").set("iterations", "50")
    world = root.find("worldbody")
    base = world.find("body[@name='base']")
    base.set("pos", numbers(scene.robot.position))
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
        rgba=".72 .76 .75 1",
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
    for obj in scene.objects:
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
        for i, value in enumerate(scene.robot.joints):
            lo, hi = model.jnt_range[i]
            if not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(
                    f"{model.joint(i).name} must be between {lo:.3f} and {hi:.3f} rad"
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
        self.visible_ids = [
            i for i in range(model.ngeom) if model.geom_group[i] not in (3, 4)
        ]

    def step(self, count=1):
        mujoco.mj_step(self.model, self.data, nstep=count)
        mujoco.mj_forward(self.model, self.data)

    def export_scene(self):
        scene = self.scene.model_copy(deep=True)
        for obj in scene.objects:
            bid = self.object_bodies[obj.id]
            obj.position = self.data.xpos[bid].tolist()
            obj.quaternion = self.data.xquat[bid].tolist()
        # Preserve commanded joint positions, not slightly deflected measured angles.
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
            contacts=int(self.data.ncon),
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

    def geometry(self):
        out = []
        reverse = {v: k for k, v in self.object_bodies.items()}
        for i in self.visible_ids:
            body = int(self.model.geom_bodyid[i])
            name = self.model.geom(i).name or f"geom_{i}"
            owner = reverse.get(
                body, "robot" if body else ("floor" if name == "floor" else "table")
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
            jointInfo=[
                dict(
                    name=self.model.joint(i).name,
                    min=float(self.model.jnt_range[i, 0]),
                    max=float(self.model.jnt_range[i, 1]),
                )
                for i in range(6)
            ],
        )

    def meshes(self):
        return compiled_meshes()
