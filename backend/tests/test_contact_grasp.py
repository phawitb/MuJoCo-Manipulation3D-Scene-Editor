"""Regression: success must come from physical support, never hidden attachment."""

import mujoco
import pytest
from backend.examples import example_scene
from backend.grasp import jaw_contacts
from backend.simulation import Simulation


def run_to_lift(example="kalas-bowl-left"):
    sim = Simulation(example_scene(example))
    sim.start_policy()
    for _ in range(1200):
        sim.step(10)
        if sim.policy.phase == "Transfer":
            return sim
        assert sim.policy.status != "failed", sim.policy.message
    raise AssertionError("No physical lift")


def test_example06_carries_without_any_attachment_constraint():
    sim = run_to_lift()
    assert sim.policy.held
    assert not sim.data.eq_active.any(), "Hidden attachment is holding the spoon"
    assert sim.policy.packet()["graspAssist"] is False


def test_opening_elevated_gripper_lets_object_fall_under_gravity():
    sim = run_to_lift()
    body = sim.object_bodies["spoon"]
    initial = sim.data.xpos[body, 2]
    # Freeze the controller, leave physics enabled, physically open the jaws.
    sim.policy.status = "idle"
    sim.data.ctrl[:] = sim.data.qpos[:6]
    sim.data.ctrl[5] = 0.8
    for _ in range(40):
        sim.step(10)
    assert sim.data.xpos[body, 2] < initial - 0.04
    assert not sim.data.eq_active.any()


@pytest.mark.parametrize("stop", ["cancel", "fail"])
def test_reported_grip_tracks_passive_physics_after_controller_stops(stop):
    sim = run_to_lift()
    assert sim.state()["task"]["grip"]["secure"]
    if stop == "cancel":
        sim.stop_policy()
        sim.running = True
    else:
        sim.policy.fail("Test interrupted grasp")
    sim.step(round(1 / sim.model.opt.timestep))
    measured = jaw_contacts(sim, "spoon")
    reported = sim.state()["task"]["grip"]
    assert not measured["secure"]
    assert measured["leftForce"] == measured["rightForce"] == 0
    assert reported == measured, "API must report current forces after passive falling"


def test_proximity_without_jaw_contact_is_not_a_grasp():
    sim = Simulation(example_scene("kalas-cup-front"))
    sim.start_policy()
    bid = sim.object_bodies["spoon"]
    adr = sim.model.jnt_qposadr[sim.model.body_jntadr[bid]]
    sim.data.qpos[adr : adr + 3] = sim.data.site("gripperframe").xpos + [0.04, 0, 0]
    sim.data.qpos[adr + 3 : adr + 7] = [1, 0, 0, 0]
    sim.data.qpos[5] = -0.03
    mujoco.mj_forward(sim.model, sim.data)
    sim.policy.contact_since = float(sim.data.time) - 0.2
    sim.policy.confirm_grasp()
    assert not sim.policy.held
    assert not sim.data.eq_active.any()


def test_loss_of_contact_fails_task_and_keeps_gravity_running():
    sim = run_to_lift()
    body = sim.object_bodies["spoon"]
    z = sim.data.xpos[body, 2]
    # Remove physical jaw support, simulating a lost grasp. No object pose writes.
    jaws = [sim.model.body("gripper").id, sim.model.body("moving_jaw_so101_v1").id]
    for geom in range(sim.model.ngeom):
        if sim.model.geom_bodyid[geom] in jaws:
            sim.model.geom_contype[geom] = sim.model.geom_conaffinity[geom] = 0
    for _ in range(30):
        sim.step(10)
    assert sim.policy.status == "failed"
    assert not sim.policy.held and not sim.policy.success
    assert sim.running, "Failure must not freeze an unsupported object in mid-air"
    assert sim.data.xpos[body, 2] < z - 0.04
    sim.step(1600)
    assert not sim.running
    assert sim.data.xpos[body, 2] < z - 0.04


def test_geometric_containment_without_physical_support_is_not_success():
    sim = Simulation(example_scene("kalas-cup-front"))
    sim.start_policy()
    body = sim.object_bodies["spoon"]
    adr = sim.model.jnt_qposadr[sim.model.body_jntadr[body]]
    target = sim.data.body("object_cup").xpos.copy()
    sim.data.qpos[adr : adr + 3] = target + [0, 0, 0.0525]
    sim.data.qpos[adr + 3 : adr + 7] = [2**-0.5, 0, 2**-0.5, 0]
    sim.data.qvel[:] = 0
    mujoco.mj_forward(sim.model, sim.data)
    sim.policy.lifted = True
    sim.policy.verify()
    assert not sim.policy.success, (
        "An unsupported spoon inside the cup volume is not settled"
    )
