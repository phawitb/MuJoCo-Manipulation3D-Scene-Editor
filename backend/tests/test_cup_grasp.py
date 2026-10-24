import numpy as np
import pytest

from backend.planning import calculate_plan, physics_fingerprint
from backend.schema import Scene, SceneObject, Task
from backend.simulation import Simulation


def cup_scene():
    return Scene(
        objects=[
            SceneObject(
                id="cup",
                name="Cup",
                asset="kalas_cup",
                position=[-0.08, -0.07, 0.7905],
                mass=0.03,
            ),
            SceneObject(
                id="plate",
                name="Plate",
                asset="kalas_plate",
                position=[-0.04, 0.10, 0.762],
                mass=0.065,
            ),
        ],
        task=Task(source="cup", target="plate"),
    )


def test_cup_rim_grasp_physically_lifts_and_places():
    sim = Simulation(cup_scene())
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert plan["verified"], plan["message"]
    assert physics_fingerprint(sim) == before
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    lifted = False
    for _ in range(3000):
        sim.step(10)
        assert not sim.data.eq_active.any()
        if sim.policy.held:
            assert sim.policy.contact["maxPenetration"] < 0.0015
            lifted |= sim.data.body("object_cup").xpos[2] > 0.86
        if sim.policy.status in ("failed", "succeeded"):
            break
    assert lifted and sim.policy.success, sim.policy.message
    assert sim.data.body("object_cup").xmat.reshape(3, 3)[2, 2] > 0.98


def test_insert_spoon_then_carry_cup_with_spoon():
    from backend.examples import example_scene
    from backend.policy import PickPlacePolicy

    scene = example_scene("kalas-rim-to-plate")
    scene.objects.append(
        SceneObject(
            id="spoon",
            name="Spoon",
            asset="kalas_spoon",
            position=[-0.07, -0.015, 0.756],
            quaternion=[0, 0, 0, 1],
            mass=0.009,
        )
    )
    sim = Simulation(scene)
    for source, target in [("spoon", "cup"), ("cup", "plate")]:
        sim.scene.task = Task(source=source, target=target)
        sim.policy = PickPlacePolicy(sim)
        plan = calculate_plan(sim)
        assert plan["verified"], (source, plan["message"])
        sim.policy.configuration = plan["configuration"]
        sim.start_policy()
        for _ in range(3000):
            sim.step(10)
            assert not sim.data.eq_active.any()
            if sim.policy.status in ("failed", "succeeded"):
                break
        assert sim.policy.success, (source, sim.policy.message)
    cup = sim.data.body("object_cup")
    spoon = sim.data.body("object_spoon")
    bowl = spoon.xpos + spoon.xmat.reshape(3, 3) @ np.array([0.0525, 0, 0])
    relative = cup.xmat.reshape(3, 3).T @ (bowl - cup.xpos)
    assert np.linalg.norm(relative[:2]) < 0.038 and -0.041 < relative[2] < 0.041
    assert cup.xmat.reshape(3, 3)[2, 2] > 0.98


def test_spilled_contents_cannot_report_success():
    import mujoco

    from backend.examples import example_scene

    scene = example_scene("kalas-cup-to-plate")
    scene.task = Task(source="source_cup", target="cup")
    sim = Simulation(scene)
    sim.step(500)
    sim.start_policy()
    assert sim.policy.contents == ["spoon"]
    bid = sim.object_bodies["spoon"]
    adr = sim.model.jnt_qposadr[sim.model.body_jntadr[bid]]
    sim.data.qpos[adr + 1] += 1
    mujoco.mj_forward(sim.model, sim.data)
    sim.policy.lifted = True
    sim.policy.update()
    assert sim.policy.status == "failed"
    assert "Contents" in sim.policy.message


def test_opening_rim_grasp_releases_cup_to_gravity():
    sim = Simulation(cup_scene())
    sim.policy.configuration = {"rim_angle": -np.pi / 2}
    sim.start_policy()
    for _ in range(1800):
        sim.step(10)
        assert sim.policy.status != "failed", sim.policy.message
        if sim.policy.phase == "Transfer":
            break
    assert sim.policy.held
    z = sim.data.body("object_cup").xpos[2]
    sim.policy.status = "idle"
    sim.data.ctrl[:] = sim.data.qpos[:6]
    sim.data.ctrl[5] = 0.8
    sim.step(500)
    assert sim.data.body("object_cup").xpos[2] < z - 0.04
    assert not sim.data.eq_active.any()


def test_tilted_cup_is_rejected_without_changing_scene():
    scene = cup_scene()
    scene.objects[0].quaternion = [2**-0.5, 0, 2**-0.5, 0]
    scene.objects[0].position[2] = 0.79
    sim = Simulation(scene)
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert not plan["verified"]
    assert physics_fingerprint(sim) == before


def test_obstructed_rim_is_not_advertised_as_runnable():
    scene = cup_scene()
    scene.objects.append(
        SceneObject(
            id="block", asset="cube", scale=2.5, position=[-0.08, -0.07, 0.90], mass=5
        )
    )
    sim = Simulation(scene)
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert not plan["verified"]
    assert physics_fingerprint(sim) == before


@pytest.mark.parametrize("variant", ["wrist", "shift", "scale", "large"])
def test_cup_grasp_uses_actual_scene_geometry(variant):
    from backend.examples import example_scene

    scene = example_scene("kalas-rim-to-plate")
    if variant == "wrist":
        scene.robot.joints = [0, -1.5, 1.5, 0.985937, 0, 0]
    if variant == "shift":
        for obj in scene.objects:
            obj.position[1] += 0.005
    if variant in ("scale", "large"):
        cup = scene.objects[0]
        cup.scale = 1.05 if variant == "scale" else 2
        cup.position[2] = 0.75 + 0.0405 * cup.scale
    sim = Simulation(scene)
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert physics_fingerprint(sim) == before
    if variant == "large":
        assert not plan["verified"]
        return
    assert plan["verified"], plan["message"]
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    for _ in range(3000):
        sim.step(17)
        if sim.policy.status in ("succeeded", "failed"):
            break
    assert sim.policy.success, sim.policy.message


def test_protruding_contents_collisions_are_checked():
    from backend.contents import contents_issue, find_contents
    from backend.examples import example_scene
    from backend.safety import collision_issue

    scene = example_scene("kalas-loaded-cup-to-plate")
    scene.objects.append(
        SceneObject(
            id="obstacle",
            name="Obstacle",
            asset="cube",
            scale=0.25,
            position=[-0.0299446, -0.09961315, 0.88571499],
        )
    )
    sim = Simulation(scene)
    sim.policy.source = "cup"
    sim.policy.target = "plate"
    sim.policy.held = True
    sim.policy.contents = find_contents(sim, "cup")
    assert sim.policy.contents == ["spoon"]
    assert contents_issue(sim, "cup", ["spoon"]) is None
    issue = collision_issue(sim)
    assert issue is not None and "Obstacle" in issue and "spoon" in issue


def test_handle_first_spoon_is_recognized_as_contents():
    from backend.contents import contents_issue, find_contents

    scene = cup_scene()
    scene.objects.append(
        SceneObject(
            id="spoon",
            asset="kalas_spoon",
            position=[-0.08, -0.07, 0.832],
            quaternion=[2**-0.5, 0, -(2**-0.5), 0],
            mass=0.009,
        )
    )
    sim = Simulation(scene)
    sim.step(1500)
    assert find_contents(sim, "cup") == ["spoon"]
    assert contents_issue(sim, "cup", ["spoon"], settled=True) is None
