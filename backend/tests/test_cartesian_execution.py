import pytest
import numpy as np
from backend.tests.test_manual_controls import control as control
from backend.modules.connection.cartesian import ToolKinematics


def prepare(s, session):
    session.id = "one"
    session.packet = lambda: {"type": "snapshot"}
    session.broadcast = lambda _: None
    s.driver.raw = s._raw([0, -0.5, 1, 0.8, 0, 0.5])
    q = s._read()
    q[4] += 0.025
    goal = ToolKinematics(session.sim).pose(q)
    waypoint = dict(goal, phase="Transfer", object_qpos=[], held=False, contents=[])
    return [waypoint]


def test_cartesian_execution_keeps_gym_clock_and_joints_independent(control):
    s, session = control
    waypoints = prepare(s, session)
    before = session.sim.data.qpos.copy()
    s.execution.start(session, session.sim, waypoints)
    assert s.execution.active and s.enabled and s.sync_mode == "off"
    assert not session.sim.running and np.array_equal(before, session.sim.data.qpos)
    assert s.execution.status()["measurement_source"] == "encoder_fk"
    s.stop("one")
    assert not s.execution.active and not s.enabled
    report = s.execution.report
    assert report["object_verified"] is False and report["outcome"] == "stopped"


def test_endpoint_completion_does_not_require_sim_joint_equality(control):
    s, session = control
    waypoints = prepare(s, session)
    # The approved task world and live Gym joint pose need not equal real state.
    session.sim.data.qpos[4] += 0.8
    s.execution.start(session, session.sim, waypoints)
    s.driver.raw = s._raw(s.manual.target)
    for _ in range(6):
        s.tick()
    assert s.execution.phase == "completed"
    assert s.fault is None
    assert not s.enabled and s.manual is None
    assert s.execution.report["last_error"]["position_mm"] < 3
    assert s.execution.report["object_verified"] is False


def test_next_world_transition_starts_at_last_measured_endpoint(control, monkeypatch):
    s, session = control
    waypoints = prepare(s, session)
    waypoints.append(dict(waypoints[0]))
    s.execution.start(session, session.sim, waypoints)
    q = list(s.manual.target)
    q[4] += 0.001
    s.driver.raw = s._raw(q)
    captured = []
    original = s.execution._motion

    def capture(measured, **kwargs):
        captured.append(kwargs.get("previous"))
        return original(measured, **kwargs)

    monkeypatch.setattr(s.execution, "_motion", capture)
    s.tick()
    assert captured and captured[0] is not None
    measured = ToolKinematics(session.sim).pose(s._read())
    assert captured[0]["quaternion"] == pytest.approx(measured["quaternion"])
    assert captured[0]["object_qpos"] == []


def test_stop_and_failed_next_waypoint_do_not_keep_old_target(control):
    s, session = control
    waypoints = prepare(s, session)
    waypoints.append(dict(waypoints[0], position=[10, 10, 10]))
    s.execution.start(session, session.sim, waypoints)
    s.driver.raw = s._raw(s.manual.target)
    s.tick()
    assert not s.enabled and not s.execution.active
    assert "unreachable" in s.fault
    before = list(s.driver.writes)
    s.tick()
    assert s.driver.writes == before


def test_task_rejects_initial_self_collision_before_writes(control):
    s, session = control
    from backend.tests.test_manual_guard import Q

    q = list(Q)
    q[2] -= 0.005
    s.driver.raw = s._raw(q)
    session.id = "one"
    session.packet = lambda: {}
    session.broadcast = lambda _: None
    goal = ToolKinematics(session.sim).pose(s._read())
    with pytest.raises(ValueError, match="collision"):
        s.execution.start(
            session,
            session.sim,
            [dict(goal, phase="Move", object_qpos=[], held=False, contents=[])],
        )
    assert not s.driver.writes and not s.enabled


def test_no_waypoints_does_not_enable_hardware(control):
    s, session = control
    with pytest.raises(ValueError, match="no tool-space"):
        s.execution.start(session, session.sim, [])
    assert not s.driver.writes


def test_carried_collision_geometry_follows_measured_tool_not_gym_joints():
    from scipy.spatial.transform import Rotation
    from backend.simulation import Simulation
    from backend.examples import example_scene
    from backend.modules.connection.execution import TaskGuard

    sim = Simulation(example_scene())
    q = [0, -0.5, 1, 0.8, 0, 0.5]
    sim.policy.held = True
    sim.policy.contents = []
    k = ToolKinematics(sim)
    reference = k.pose(q)
    guard = TaskGuard(sim, reference)
    q[0] += 0.1
    # Inspect geometry even if that configuration has an object contact.
    try:
        guard.observe(q)
    except ValueError:
        pass
    before = np.array(sim.data.qpos[6:9])
    p0 = np.array(reference["position"])
    after = k.pose(q)
    r0 = Rotation.from_quat(reference["quaternion"])
    r1 = Rotation.from_quat(after["quaternion"])
    expected = np.array(after["position"]) + r1.apply(r0.inv().apply(before - p0))
    assert guard.data.qpos[6:9] == pytest.approx(expected)


def test_releasing_object_estimate_waits_for_jaw_opening():
    from backend.simulation import Simulation
    from backend.examples import example_scene
    from backend.modules.connection.execution import TaskGuard

    sim = Simulation(example_scene())
    q = [0, -0.5, 1, 0.8, 0, 0]
    previous = ToolKinematics(sim).pose(q)
    previous["object_qpos"] = sim.data.qpos[6:].tolist()
    sim.data.qpos[8] -= 0.02
    target = dict(previous, opening_rad=0.1, phase="Release")
    guard = TaskGuard(sim, target, previous=previous)
    try:
        guard.observe(q)
    except ValueError:
        pass
    assert guard.data.qpos[8] == pytest.approx(previous["object_qpos"][2])
    q[5] = 0.05
    try:
        guard.observe(q)
    except ValueError:
        pass
    assert guard.data.qpos[8] == pytest.approx(previous["object_qpos"][2] - 0.01)


def test_retreat_collision_world_advances_with_tool_not_before_it():
    from backend.simulation import Simulation
    from backend.examples import example_scene
    from backend.modules.connection.execution import TaskGuard

    sim = Simulation(example_scene())
    q = [0, -0.5, 1, 0.8, 0, 0.5]
    k = ToolKinematics(sim)
    previous = k.pose(q)
    previous["object_qpos"] = sim.data.qpos[6:].tolist()
    sim.data.qpos[8] -= 0.02
    next_q = list(q)
    next_q[3] += 0.05
    target = dict(k.pose(next_q), phase="Retreat")
    guard = TaskGuard(sim, target, previous=previous)
    try:
        guard.observe(q)
    except ValueError:
        pass
    assert guard.data.qpos[8] == pytest.approx(previous["object_qpos"][2])
    try:
        guard.observe(next_q)
    except ValueError:
        pass
    assert guard.data.qpos[8] == pytest.approx(previous["object_qpos"][2] - 0.02)
