import numpy as np
import pytest
from backend.schema import Scene
from backend.simulation import Simulation
from backend.examples import example_scene


def test_example_physically_lifts_releases_and_settles():
    sim = Simulation(example_scene())
    start = sim.data.qpos[:6].copy()
    source = sim.scene.task.source
    bid = sim.object_bodies[source]
    z0 = sim.data.xpos[bid, 2]
    sim.start_policy()
    max_z = z0
    attached = False
    for _ in range(1500):
        sim.step(10)
        max_z = max(max_z, sim.data.xpos[bid, 2])
        attached |= bool(sim.data.eq_active.any())
        if sim.policy.status in ('succeeded', 'failed'):
            break
    assert sim.policy.status == 'succeeded', sim.policy.packet()
    assert max_z > z0 + .07
    assert attached and not sim.data.eq_active.any()
    assert np.linalg.norm(sim.data.qpos[:5] - start[:5]) > .2
    assert sim.policy.packet()['success'] is True


def test_task_validation_and_cancel():
    sim = Simulation()
    with pytest.raises(ValueError, match='[Ss]elect'):
        sim.start_policy()
    sim.load(example_scene())
    sim.start_policy()
    sim.step(100)
    sim.stop_policy()
    assert not sim.running and not sim.data.eq_active.any()
    assert sim.policy.status == 'cancelled'
    assert Scene.model_validate(sim.export_scene().model_dump())


def test_wrist_camera_follows_actual_robot():
    sim = Simulation()
    a = sim.state()['cameras']['wrist']['position']
    sim.data.qpos[0] += .4
    import mujoco
    mujoco.mj_forward(sim.model, sim.data)
    b = sim.state()['cameras']['wrist']['position']
    assert not np.allclose(a, b)


def test_unreachable_task_does_not_move_or_activate_grasp():
    scene=example_scene()
    scene.objects[0].position=[2,2,.756]
    sim=Simulation(scene)
    before=sim.data.qpos.copy()
    with pytest.raises(ValueError,match='reach'):
        sim.start_policy()
    assert np.array_equal(before,sim.data.qpos)
    assert not sim.running and not sim.data.eq_active.any()


def test_cancel_releases_held_object_and_does_not_report_success():
    sim=Simulation(example_scene());sim.start_policy()
    for _ in range(250): sim.step(10)
    assert sim.policy.held
    sim.stop_policy()
    assert not sim.data.eq_active.any()
    assert not sim.policy.success
    assert sim.policy.status=='cancelled'


@pytest.mark.parametrize('offset', [-.005, .0, .005])
def test_example_repeatability_with_small_placement_variations(offset):
    scene=example_scene();scene.objects[0].position[0]+=offset
    sim=Simulation(scene);sim.start_policy()
    for _ in range(1000):
        sim.step(10)
        if sim.policy.status in ('succeeded','failed'): break
    assert sim.policy.success, sim.policy.packet()
