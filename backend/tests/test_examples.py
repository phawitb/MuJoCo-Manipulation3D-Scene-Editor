"""Every advertised task is rehearsed and then physically executed independently."""

import math
import numpy as np
import pytest
from backend.examples import example_catalog, example_scene
from backend.planning import calculate_plan, physics_fingerprint
from backend.simulation import Simulation


@pytest.mark.parametrize("batch", [1, 17, 33])
@pytest.mark.parametrize("example_id", [e["id"] for e in example_catalog()])
def test_examples_plan_and_execute(example_id, batch):
    sim = Simulation(example_scene(example_id))
    initial = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert plan["verified"], (example_id, plan["message"])
    assert initial == physics_fingerprint(sim)
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    source_body = f"object_{sim.scene.task.source}"
    original = sim.data.body(source_body).xpos[2]
    max_z = original
    held = False
    longest_gap = gap = 0.0
    min_force = float("inf")
    for _ in range(int(30 / (batch * sim.model.opt.timestep))):
        sim.step(batch)
        max_z = max(max_z, sim.data.body(source_body).xpos[2])
        held |= sim.policy.held
        assert not sim.data.eq_active.any(), (
            "No invisible attachment may carry the load"
        )
        if sim.policy.held:
            grip = sim.policy.contact
            gap = 0 if grip["secure"] else gap + batch * sim.model.opt.timestep
            longest_gap = max(longest_gap, gap)
            if grip["secure"]:
                min_force = min(min_force, grip["leftForce"], grip["rightForce"])
            assert grip["maxPenetration"] < 0.0015
        if sim.policy.status in ("failed", "succeeded"):
            break
    assert held and max_z > original + 0.06
    assert longest_gap <= 0.10
    assert min_force > 0.02
    assert sim.policy.success, (example_id, sim.policy.packet())
    assert not sim.data.eq_active.any()
    assert np.linalg.norm(sim.data.body(source_body).cvel) < 0.2
    print(
        example_id,
        f"PASS batch={batch} {sim.data.time:.2f}s attempts={plan['attempts']} lift={max_z - original:.3f}m gap={longest_gap:.3f}s min_force={min_force:.3f}N",
    )


@pytest.mark.parametrize("angle", [0, 45, 90, 270])
def test_user_arranged_and_rotated_spoon(angle):
    scene = example_scene("kalas-cup-front")
    scene.name = "Custom user scene"
    scene.objects[1].position[:2] = [-0.03, 0.08]
    a = math.radians(angle) / 2
    scene.objects[0].quaternion = [math.cos(a), 0, 0, math.sin(a)]
    sim = Simulation(scene)
    plan = calculate_plan(sim)
    assert plan["verified"], plan["message"]
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    for _ in range(2000):
        sim.step(17)
        if sim.policy.status in ("failed", "succeeded"):
            break
    assert sim.policy.success, sim.policy.packet()


def test_blocked_task_is_not_advertised_as_runnable():
    from backend.schema import SceneObject

    scene = example_scene("kalas-cup-front")
    scene.objects.append(
        SceneObject(
            id="obstruction",
            asset="cube",
            scale=3,
            position=[-0.08, -0.07, 0.83],
            mass=10,
        )
    )
    sim = Simulation(scene)
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert not plan["verified"]
    assert before == physics_fingerprint(sim)


def test_custom_robot_base_pose_uses_world_kinematics():
    scene = example_scene("kalas-cup-front")
    scene.robot.position[0] -= 0.01
    angle = math.radians(5) / 2
    scene.robot.quaternion = [math.cos(angle), 0, 0, math.sin(angle)]
    sim = Simulation(scene)
    plan = calculate_plan(sim)
    assert plan["verified"], plan["message"]
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    for _ in range(2000):
        sim.step(17)
        if sim.policy.status in ("failed", "succeeded"):
            break
    assert sim.policy.success, sim.policy.packet()
