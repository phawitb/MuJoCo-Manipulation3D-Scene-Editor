"""Tool-space goals retain joint, path and command-lifetime guards."""

import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from backend.tests.test_manual_controls import control as control
from backend.modules.connection.cartesian import ToolKinematics, pose_error, arrived
from backend.modules.connection.schemas import ToolTarget


def goal_for(s, session, q):
    return dict(
        session_id="one",
        control_epoch=s.control_epoch,
        **ToolKinematics(session.sim).pose(q)
    )


def test_fk_matches_mujoco_without_mutating_scene(control):
    import mujoco

    s, session = control
    before = session.sim.data.qpos.copy()
    q = s._read()
    pose = ToolKinematics(session.sim).pose(q)
    scratch = mujoco.MjData(session.sim.model)
    scratch.qpos[:] = before
    scratch.qpos[:6] = q
    mujoco.mj_fwdPosition(session.sim.model, scratch)
    assert pose["position"] == pytest.approx(scratch.site("gripperframe").xpos)
    assert np.array_equal(before, session.sim.data.qpos)


def test_reachable_goal_solved_from_measured_seed_and_gym_not_moved(control):
    s, session = control
    q = s._read()
    target = q.copy()
    target[4] += 0.035
    before = session.sim.data.qpos.copy()
    result = s.move_tool(ToolTarget(**goal_for(s, session, target)))
    assert result["tool"]["measurement_source"] == "encoder_fk"
    assert result["tool"]["object_verified"] is False
    solved = s.manual.target
    error = pose_error(
        ToolKinematics(session.sim).pose(solved), goal_for(s, session, target)
    )
    assert error["position_mm"] < 1 and error["orientation_deg"] < 0.5
    assert np.array_equal(before, session.sim.data.qpos)


def test_arrival_uses_position_orientation_and_jaw_not_sim_joint_angles():
    pose = dict(position=[0, 0, 1], quaternion=[0, 0, 0, 1], opening_rad=0.5)
    assert arrived(pose_error(pose, pose))
    for key, value in [
        ("position", [0.02, 0, 1]),
        ("quaternion", Rotation.from_euler("x", 15, degrees=True).as_quat().tolist()),
        ("opening_rad", 0.7),
    ]:
        assert not arrived(pose_error(pose, dict(pose, **{key: value})))


@pytest.mark.parametrize("reason", ["unreachable", "epoch", "range", "collision"])
def test_rejected_tool_goal_never_writes(control, reason):
    s, session = control
    q = s._read()
    data = goal_for(s, session, q)
    if reason == "unreachable":
        data["position"] = [10, 10, 10]
    if reason == "epoch":
        data["control_epoch"] -= 1
    if reason == "range":
        data["opening_rad"] = 1.74
        s.calibration.joints[5].raw_max = 2050
    if reason == "collision":
        session.sim.scene.robot.pedestal_height = 0
        # Reject an otherwise reachable target by changing the whole-arm guard.
        q[1] += 0.15
        data = goal_for(s, session, q)
    with pytest.raises(ValueError):
        s.move_tool(ToolTarget(**data))
    assert not s.driver.writes


def test_stop_and_expired_lease_cancel_cartesian_goal(control):
    s, session = control
    q = s._read()
    q[4] += 0.03
    goal = ToolTarget(**goal_for(s, session, q))
    s.move_tool(goal)
    s.stop("one")
    before = list(s.driver.writes)
    with pytest.raises(ValueError, match="expired"):
        s.move_tool(goal)
    s.tick()
    assert s.driver.writes == before and s.manual is None
    goal.control_epoch = s.control_epoch
    s.move_tool(goal)
    s.lease_until = 0
    s.tick()
    assert not s.enabled and s.manual is None


def test_tool_api_requires_epoch_and_rejects_bad_rotation(control):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.modules.connection.routes import create_router

    s, session = control
    app = FastAPI()
    app.include_router(create_router(s))
    client = TestClient(app)
    data = goal_for(s, session, s._read())
    data.pop("control_epoch")
    assert client.post("/api/connection/tool-target", json=data).status_code == 422
    data["control_epoch"] = s.control_epoch
    data["quaternion"] = [0, 0, 0, 0]
    assert client.post("/api/connection/tool-target", json=data).status_code == 422
    assert not s.driver.writes


def test_rehearsal_exports_tool_goals_and_collision_world_without_joint_replay(control):
    from backend.planning import tool_waypoint

    s, session = control
    q = s._read()
    session.sim.data.qpos[:6] = q
    w = tool_waypoint(session.sim)
    assert "joints" not in w
    assert w["position"] == pytest.approx(
        ToolKinematics(session.sim).pose(q)["position"]
    )
    assert len(w["quaternion"]) == 4 and w["opening_rad"] == q[5]
    assert w["object_qpos"] == session.sim.data.qpos[6:].tolist()


def test_ik_reserves_encoder_rounding_at_joint_limits(control):
    from backend.modules.connection.manual import MotionGuard

    s, session = control
    session.sim.model.jnt_range[4, 1] = 0.0195
    q = [0, -0.5, 1, 0.8, 0.0195, 0.5]
    goal = ToolKinematics(session.sim).pose(q)
    solved = ToolKinematics(session.sim).solve(
        goal,
        q,
        s._control_limits(),
        MotionGuard(session.sim, q),
        resolution=[c.radians_per_tick for c in s.calibration.joints],
    )
    command = s._raw(solved)
    quantized = [s._angle(i, r) for i, r in enumerate(command)]
    assert all(lo <= v <= hi for v, (lo, hi) in zip(quantized, s._control_limits()))


def test_joint_command_replaces_cartesian_controller_after_arrival(control):
    from backend.modules.connection.manual import ManualMotion

    s, session = control
    q = s._read()
    s.move_tool(ToolTarget(**goal_for(s, session, q)))
    for _ in range(6):
        s.tick()
    assert s.manual.phase == "holding"
    q[4] += 0.08
    s.move("one", q, control_epoch=s.control_epoch)
    assert type(s.manual) is ManualMotion
    s.manual.last -= 0.1
    before = len(s.driver.writes)
    s.tick()
    assert len(s.driver.writes) > before


def test_cartesian_stop_never_moves_to_bias_using_finished_gym_world(
    control, monkeypatch
):
    s, session = control
    q = s._read()
    s.move_tool(ToolTarget(**goal_for(s, session, q)))
    s.tracker.bias[4] = 0.05
    s.target_rad = list(q)
    s.target_rad[4] += 0.05
    checked = []
    monkeypatch.setattr(s.bridge, "validate", lambda *args: checked.append(args))
    measured = list(s.driver.raw)
    s.stop("one")
    assert s.driver.writes[-1] == ("goals", measured)
    assert not checked and s.tracker is None
    assert not s.enabled and s.manual is None
