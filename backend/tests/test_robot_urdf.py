"""The connection viewer must use the same joint frames as the Gym model."""

from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "assets/so101"


def transform(origin):
    result = np.eye(4)
    if origin is not None:
        result[:3, 3] = np.fromstring(origin.get("xyz", "0 0 0"), sep=" ")
        result[:3, :3] = Rotation.from_euler(
            "xyz", np.fromstring(origin.get("rpy", "0 0 0"), sep=" ")
        ).as_matrix()
    return result


def test_urdf_matches_gym_at_varied_joint_angles():
    robot = ET.parse(MODEL / "so101.urdf").getroot()
    model = mujoco.MjModel.from_xml_path(str(MODEL / "so101.xml"))
    data = mujoco.MjData(model)
    rng = np.random.default_rng(101)
    poses = [
        np.zeros(6),
        *rng.uniform(model.jnt_range[:, 0], model.jnt_range[:, 1], (25, 6)),
    ]
    for q in poses:
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        frames = {"base": np.eye(4)}
        for joint in robot.findall("joint"):
            local = transform(joint.find("origin"))
            if joint.get("type") != "fixed":
                name = joint.get("name")
                axis = np.fromstring(joint.find("axis").get("xyz"), sep=" ")
                local[:3, :3] @= Rotation.from_rotvec(
                    axis * q[model.joint(name).id]
                ).as_matrix()
                np.testing.assert_allclose(
                    [float(joint.find("limit").get(k)) for k in ("lower", "upper")],
                    model.joint(name).range,
                )
            child = joint.find("child").get("link")
            frames[child] = frames[joint.find("parent").get("link")] @ local
        for link in robot.findall("link"):
            name = link.get("name")
            np.testing.assert_allclose(
                frames[name][:3, 3], data.body(name).xpos, atol=1e-10
            )
            np.testing.assert_allclose(
                frames[name][:3, :3], data.body(name).xmat.reshape(3, 3), atol=1e-10
            )
    meshes = robot.findall(".//mesh")
    assert len(meshes) == 18
    for mesh in meshes:
        assert (MODEL / mesh.get("filename")).is_file()
    assert (
        ROOT / "frontend/public/robots/so101/so101.urdf"
    ).resolve() == MODEL / "so101.urdf"
