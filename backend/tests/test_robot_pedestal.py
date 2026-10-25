"""Mount correction must change physics, rendering and persisted scenes together."""

import mujoco
import numpy as np
import pytest
from backend.schema import Scene
from backend.simulation import Simulation
from backend.sessions import Command, Session
from backend.examples import example_catalog

CONTACT_POSE = [
    -0.08666991451553872,
    -1.671272068401406,
    1.6942817802196908,
    1.2977477465512524,
    -1.5454856437947835,
    -0.0030679615757712823,
]


def lowest_visual_jaw(sim):
    lows = []
    for name in ("gripper", "moving_jaw_so101_v1"):
        body = sim.model.body(name).id
        for g in range(sim.model.ngeom):
            if (
                sim.model.geom_bodyid[g] != body
                or sim.model.geom_group[g] != 2
                or sim.model.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH
            ):
                continue
            mesh = sim.model.geom_dataid[g]
            start, count = sim.model.mesh_vertadr[mesh], sim.model.mesh_vertnum[mesh]
            points = (
                sim.model.mesh_vert[start : start + count]
                @ sim.data.geom_xmat[g].reshape(3, 3).T
                + sim.data.geom_xpos[g]
            )
            lows.append(points[:, 2].min())
    return min(lows)


def test_mount_lifts_all_links_without_changing_joints_and_corrects_contact():
    baseline = Simulation()
    raised_scene = Scene.model_validate({"robot": {"pedestal_height": 0.0222}})
    raised = Simulation(raised_scene)
    for sim in (baseline, raised):
        # Observe the real encoder pose without inventing joint-limit corrections.
        sim.data.qpos[:6] = CONTACT_POSE
        mujoco.mj_forward(sim.model, sim.data)
    assert lowest_visual_jaw(baseline) < baseline.scene.table.height - 0.02
    assert abs(lowest_visual_jaw(raised) - raised.scene.table.height) < 0.0001
    for name in (
        "base",
        "shoulder",
        "upper_arm",
        "lower_arm",
        "wrist",
        "gripper",
        "moving_jaw_so101_v1",
    ):
        np.testing.assert_allclose(
            raised.data.body(name).xpos - baseline.data.body(name).xpos,
            [0, 0, 0.0222],
            atol=1e-12,
        )
    np.testing.assert_array_equal(raised.data.qpos, baseline.data.qpos)
    geom = raised.model.geom("robot_pedestal")
    assert geom.contype[0] != 0 and geom.conaffinity[0] != 0
    assert any(
        g["name"] == "robot_pedestal" and g["owner"] == "robot"
        for g in raised.geometry()
    )
    assert not any(
        c.dist < -0.001 and raised.model.geom(c.geom1).name == "table"
        for c in raised.data.contact
    )


def test_mount_survives_examples_reset_and_scene_round_trip():
    s = Session()
    s.execute(Command(type="robot", patch={"pedestal_height": 0.0222}))
    for cmd in [Command(type="reset")] + [
        Command(type="example", exampleId=e["id"]) for e in example_catalog()
    ]:
        packet = s.execute(cmd)
        assert packet["scene"]["robot"]["pedestal_height"] == 0.0222
        assert s.sim.model.geom("robot_pedestal").size[2] > 0
    assert (
        Scene.model_validate(s.sim.export_scene().model_dump()).robot.pedestal_height
        == 0.0222
    )


def test_mount_bounds_and_legacy_scene():
    assert Scene().robot.pedestal_height == 0
    for height in (-0.01, 0.21, float("nan")):
        with pytest.raises(ValueError):
            Scene.model_validate({"robot": {"pedestal_height": height}})


def test_encoder_view_mount_matches_gym_geometry():
    from types import SimpleNamespace
    from backend.modules.connection.bridge import GymBridge

    s = Session()
    s.execute(Command(type="robot", patch={"pedestal_height": 0.0222}))
    mount = GymBridge(SimpleNamespace(get=lambda _: s), s.id).mount()
    base = s.sim.data.body("base").xpos
    np.testing.assert_allclose(mount["table_z"], s.sim.scene.table.height - base[2])
    gid = s.sim.model.geom("robot_pedestal").id
    np.testing.assert_allclose(
        mount["pedestal"]["position"], s.sim.data.geom_xpos[gid] - base
    )
    np.testing.assert_allclose(
        mount["pedestal"]["size"], 2 * s.sim.model.geom_size[gid]
    )
    np.testing.assert_allclose(mount["quaternion"], s.sim.data.body("base").xquat)
