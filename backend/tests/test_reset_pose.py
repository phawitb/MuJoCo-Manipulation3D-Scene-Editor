"""Saved robot reset positions survive resets, examples and scene round trips."""

import numpy as np
import pytest
from backend.sessions import Command, Session
from backend.examples import example_catalog
from backend.schema import Scene
from backend.simulation import Simulation


def test_saved_pose_is_used_by_reset_and_every_example():
    session = Session()
    pose = [0.12, -0.8, 0.9, -0.4, 0.15, 0.3]
    session.execute(Command(type="robot", patch={"reset_joints": pose}))
    for cmd in [Command(type="reset")] + [
        Command(type="example", exampleId=e["id"]) for e in example_catalog()
    ]:
        session.execute(Command(type="robot", joints=[0, 0, 0, 0, 0, 0]))
        result = session.execute(cmd)
        assert result["scene"]["robot"]["reset_joints"] == pose
        assert result["scene"]["robot"]["joints"] == pose
        np.testing.assert_allclose(session.sim.data.qpos[:6], pose)
    restored = Simulation(Scene.model_validate(session.sim.export_scene().model_dump()))
    assert restored.scene.robot.reset_joints == pose


def test_invalid_saved_pose_does_not_replace_live_scene():
    session = Session()
    before = session.sim.export_scene().model_dump()
    with pytest.raises(ValueError, match="reset_joints.*shoulder_pan"):
        session.execute(
            Command(type="robot", patch={"reset_joints": [4, 0, 0, 0, 0, 0]})
        )
    assert session.sim.export_scene().model_dump() == before


def test_default_is_compact_folded_and_stable_without_contacts():
    sim = Simulation()
    # Folded wrist stays near the base, above the tabletop, with closed jaws.
    grip = sim.data.body("gripper").xpos
    assert abs(grip[0] - sim.scene.robot.position[0]) < 0.15
    assert grip[2] > sim.scene.table.height + 0.1
    assert abs(sim.data.qpos[5]) < 0.05
    initial = sim.data.qpos.copy()
    for _ in range(200):
        sim.step(10)
        assert sim.data.ncon == 0
    np.testing.assert_allclose(sim.data.qpos, initial, atol=0.002)
    assert np.linalg.norm(sim.data.qvel) < 0.001


def test_legacy_scene_keeps_current_joints_and_gets_folded_reset():
    scene = Scene.model_validate({"robot": {"joints": [0, -0.7, 0.7, 0.3, 0, 0.6]}})
    sim = Simulation(scene)
    assert sim.scene.robot.joints == [0, -0.7, 0.7, 0.3, 0, 0.6]
    assert sim.scene.robot.reset_joints == Scene().robot.joints
