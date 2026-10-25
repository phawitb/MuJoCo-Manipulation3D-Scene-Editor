import numpy as np
import pytest
from backend.schema import Scene
from backend.simulation import Simulation
from backend.examples import example_scene


@pytest.mark.parametrize("elapsed", [0.81, 2.4])
def test_release_waits_for_open_jaw_or_fails_without_retreat(elapsed):
    sim = Simulation(example_scene())
    sim.start_policy()
    policy = sim.policy
    target = sim.data.qpos[:6].copy()
    target[5] = 0.8
    policy.steps = [("Release", target, 0.8), ("Retreat", target, 1.7)]
    policy.index = 0
    policy.phase = "Release"
    policy.started = float(sim.data.time) - elapsed
    policy.start_q = sim.data.qpos[:6].copy()
    sim.data.qpos[5] = 0.1
    policy.update()
    assert policy.index == 0
    assert sim.data.ctrl[5] == pytest.approx(0.8)
    if elapsed > 2.3:
        assert policy.status == "failed"
        assert "open" in policy.message.lower()
    else:
        assert policy.status == "running"
        sim.data.qpos[5] = 0.8
        policy.update()
        assert policy.index == 1


def test_example_physically_lifts_releases_and_settles():
    sim = Simulation(example_scene())
    start = sim.data.qpos[:6].copy()
    source = sim.scene.task.source
    bid = sim.object_bodies[source]
    z0 = sim.data.xpos[bid, 2]
    sim.start_policy()
    max_z = z0
    attached = False
    for _ in range(3000):
        sim.step(10)
        max_z = max(max_z, sim.data.xpos[bid, 2])
        attached |= sim.policy.held
        assert not sim.data.eq_active.any()
        if sim.policy.status in ("succeeded", "failed"):
            break
    assert sim.policy.status == "succeeded", sim.policy.packet()
    assert max_z > z0 + 0.07
    assert attached and not sim.data.eq_active.any()
    assert np.linalg.norm(sim.data.qpos[:5] - start[:5]) > 0.2
    assert sim.policy.packet()["success"] is True


def test_task_validation_and_cancel():
    sim = Simulation()
    with pytest.raises(ValueError, match="[Ss]elect"):
        sim.start_policy()
    sim.load(example_scene())
    sim.start_policy()
    sim.step(100)
    sim.stop_policy()
    assert not sim.running and not sim.data.eq_active.any()
    assert sim.policy.status == "cancelled"
    assert Scene.model_validate(sim.export_scene().model_dump())


def test_wrist_camera_follows_actual_robot():
    sim = Simulation()
    a = sim.state()["cameras"]["wrist"]["position"]
    sim.data.qpos[0] += 0.4
    import mujoco

    mujoco.mj_forward(sim.model, sim.data)
    b = sim.state()["cameras"]["wrist"]["position"]
    assert not np.allclose(a, b)


def test_unreachable_task_does_not_move_or_activate_grasp():
    scene = example_scene()
    scene.objects[0].position = [2, 2, 0.756]
    sim = Simulation(scene)
    before = sim.data.qpos.copy()
    from backend.planning import calculate_plan

    plan = calculate_plan(sim)
    assert not plan["verified"] and "reach" in plan["message"].lower()
    assert np.array_equal(before, sim.data.qpos)
    assert not sim.running and not sim.data.eq_active.any()


def test_cancel_releases_held_object_and_does_not_report_success():
    sim = Simulation(example_scene())
    sim.start_policy()
    for _ in range(700):
        sim.step(10)
    assert sim.policy.held
    sim.stop_policy()
    assert not sim.data.eq_active.any()
    assert not sim.policy.success
    assert sim.policy.status == "cancelled"


@pytest.mark.parametrize("offset", [-0.005, 0.0, 0.005])
def test_example_repeatability_with_small_placement_variations(offset):
    scene = example_scene()
    scene.objects[0].position[0] += offset
    sim = Simulation(scene)
    sim.start_policy()
    for _ in range(3000):
        sim.step(10)
        if sim.policy.status in ("succeeded", "failed"):
            break
    assert sim.policy.success, sim.policy.packet()
