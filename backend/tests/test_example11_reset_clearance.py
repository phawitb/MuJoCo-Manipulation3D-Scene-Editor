"""Cup extraction must also work from the user's downward-wrist reset pose."""

import numpy as np
import pytest
from backend.examples import example_scene
from backend.planning import calculate_plan, physics_fingerprint
from backend.sessions import Session, Command
from backend.simulation import Simulation


@pytest.mark.parametrize("wrist", [0.8, 0.985937, 1.1])
def test_example11_from_saved_downward_wrist_has_clearance_and_runs(wrist):
    session = Session()
    pose = [0, -1.5, 1.5, wrist, 0, 0]
    session.execute(Command(type="robot", patch={"reset_joints": pose}))
    session.execute(Command(type="example", exampleId="kalas-cup-to-plate"))
    sim = session.sim
    assert sim.scene.robot.joints == pose
    objects = set(sim.object_bodies.values())
    for contact in sim.data.contact:
        a, b = (int(sim.model.geom_bodyid[g]) for g in contact.geom)
        assert not (
            contact.dist < 0
            and ((a in objects and 0 < b < 9) or (b in objects and 0 < a < 9))
        )
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert plan["verified"], plan["message"]
    assert physics_fingerprint(sim) == before
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    start_cup = sim.data.body("object_source_cup").xpos.copy()
    held = False
    for _ in range(3000):
        sim.step(10)
        held |= sim.policy.held
        assert not sim.data.eq_active.any()
        if sim.policy.status in ("failed", "succeeded"):
            break
    assert held and sim.policy.success, sim.policy.packet()
    assert np.linalg.norm(sim.data.body("object_source_cup").xpos - start_cup) < 0.005


def test_initial_overlap_names_the_object_and_robot_part_without_moving_scene():
    scene = example_scene("kalas-cup-to-plate")
    # Original cup/utensil coordinates from the reported failing scene.
    scene.objects[0].position = [-0.09978705, 0.10469775, 0.82612671]
    scene.objects[2].position = [-0.12, 0.09, 0.79044761]
    scene.robot.joints = [0, -1.5, 1.5, 0.985937, 0, 0]
    sim = Simulation(scene)
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert not plan["verified"]
    assert "Starting pose" in plan["message"]
    assert "Source · KALAS cup" in plan["message"]
    assert "wrist camera" in plan["message"]
    assert plan["attempts"] == 0
    assert physics_fingerprint(sim) == before
