import pytest
import numpy as np
import mujoco
from backend.examples import example_scene
from backend.simulation import Simulation
from backend.sessions import Session, Command
from backend.planning import calculate_plan, physics_fingerprint


def test_export_uses_measured_joints_not_unreachable_actuator_targets():
    sim = Simulation()
    measured = sim.data.qpos[:6].copy()
    sim.data.ctrl[3] = 1.4
    np.testing.assert_allclose(sim.export_scene().robot.joints, measured)


def test_changing_instruction_keeps_full_physical_state():
    session = Session()
    session.execute(Command(type="example", exampleId="kalas-cup-to-plate"))
    sim = session.sim
    sim.step(100)
    sim.data.ctrl[3] += 0.1
    qpos, qvel, ctrl = sim.data.qpos.copy(), sim.data.qvel.copy(), sim.data.ctrl.copy()
    time = sim.data.time
    session.execute(Command(type="task", source="spoon", target="source_cup"))
    np.testing.assert_array_equal(sim.data.qpos, qpos)
    np.testing.assert_array_equal(sim.data.qvel, qvel)
    np.testing.assert_array_equal(sim.data.ctrl, ctrl)
    assert sim.data.time == time
    assert sim.scene.task.target == "source_cup"


@pytest.mark.parametrize("wrist", [-1.5, 0.985937])
def test_example11_finishes_without_self_contact_and_can_return_spoon(wrist):
    scene = example_scene("kalas-cup-to-plate")
    scene.robot.joints[3] = wrist
    sim = Simulation(scene)
    for destination in ["cup", "source_cup"]:
        sim.scene.task.target = destination
        from backend.policy import PickPlacePolicy

        sim.policy = PickPlacePolicy(sim)
        before = physics_fingerprint(sim)
        plan = calculate_plan(sim)
        assert plan["verified"], (destination, plan["message"])
        assert physics_fingerprint(sim) == before
        sim.policy.configuration = plan["configuration"]
        sim.start_policy()
        for _ in range(30000):
            sim.step()
            objects = set(sim.object_bodies.values())
            robot = set(range(1, sim.model.nbody)) - objects
            for contact in sim.data.contact:
                a, b = [int(sim.model.geom_bodyid[g]) for g in contact.geom]
                assert not (a in robot and b in robot and contact.dist < -0.00002), (
                    sim.policy.phase,
                    sim.model.body(a).name,
                    sim.model.body(b).name,
                    contact.dist,
                )
            if sim.policy.status in ("failed", "succeeded"):
                break
        assert sim.policy.success, sim.policy.message
        assert np.max(np.abs(sim.data.qpos[:5] - sim.data.ctrl[:5])) < 0.01


def test_clear_endpoints_cannot_hide_self_collision_between_waypoints():
    from backend.safety import collision_issue, swept_collision

    sim = Simulation()
    start = np.array(
        [0.9567238247, -1.5254216118, 0.9217664821, 1.3436752959, 0.5446964331, 0.8]
    )
    end = np.array(
        [-0.0237978247, -1.7451163882, 0.9399595179, 1.5576647041, 2.5266975669, 0.8]
    )
    scratch = mujoco.MjData(sim.model)
    before = physics_fingerprint(sim)
    for q in [start, end]:
        scratch.qpos[:6] = q
        mujoco.mj_forward(sim.model, scratch)
        assert collision_issue(sim, scratch, kinematic=True) is None
    assert "self-collision" in swept_collision(sim, start, end)
    assert before == physics_fingerprint(sim)


def test_runtime_contact_guard_overrides_terminal_success_and_keeps_gravity(
    monkeypatch,
):
    sim = Simulation(example_scene("kalas-cup-to-plate"))
    sim.start_policy()
    # Reported old final command: an unexpected physical overlap must stop the
    # arm even on the very step in which the task claims to have completed.
    sim.data.qpos[:6] = [0.466463, -1.635269, 0.930863, 1.45067, 1.535697, 0.8]
    sim.data.ctrl[:] = sim.data.qpos[:6]
    mujoco.mj_forward(sim.model, sim.data)

    def premature_success():
        sim.policy.status = "succeeded"
        sim.policy.success = True
        sim.running = False

    monkeypatch.setattr(sim.policy, "update", premature_success)
    sim.step()
    assert sim.policy.status == "failed" and not sim.policy.success
    assert "self-collision" in sim.policy.message
    assert sim.running and not sim.policy.held
    assert not sim.data.eq_active.any()
    # The controller holds measured angles, never the penetrating command.
    np.testing.assert_allclose(sim.data.ctrl[:5], sim.data.qpos[:5])


def test_arm_table_and_other_object_contacts_are_rejected():
    from backend.safety import collision_issue
    from backend.schema import SceneObject

    scene = example_scene("kalas-cup-front")
    base = Simulation(scene)
    position = base.data.body("gripper").xpos.tolist()
    scene.objects.append(
        SceneObject(id="obstacle", name="Obstacle", asset="cube", position=position)
    )
    sim = Simulation(scene)
    assert "Obstacle" in collision_issue(sim)
    # A raised tabletop intersecting the folded arm is environment contact.
    scene.objects.pop()
    scene.table.height = position[2]
    sim = Simulation(scene)
    assert "table" in collision_issue(sim)


def test_tracking_error_does_not_advance_to_next_waypoint():
    sim = Simulation(example_scene("kalas-cup-front"))
    sim.start_policy()
    blocked = sim.data.qpos[:6].copy()
    blocked[0] += 0.2
    sim.policy.steps = [("Approach", blocked, 0.1)]
    sim.policy.started = -1
    sim.policy.update()
    assert sim.policy.status == "failed"
    assert "did not reach" in sim.policy.message
    assert sim.policy.index == 0


def test_joint_limits_are_checked_before_rehearsal_without_mutation():
    sim = Simulation(example_scene("kalas-cup-front"))
    sim.data.qpos[0] = sim.model.jnt_range[0, 1] + 0.05
    mujoco.mj_forward(sim.model, sim.data)
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert not plan["verified"] and plan["attempts"] == 0
    assert "Joint limit" in plan["message"]
    assert before == physics_fingerprint(sim)


def test_terminal_batch_cannot_continue_unchecked_into_self_collision(monkeypatch):
    from backend.safety import collision_issue

    sim = Simulation(example_scene("kalas-cup-to-plate"))
    sim.start_policy()
    sim.data.qpos[:6] = [0.466463, -1.635269, 0.930863, 1.38272855843, 1.535697, 0.8]
    sim.data.qvel[3] = 1
    sim.data.ctrl[:] = sim.data.qpos[:6]
    mujoco.mj_forward(sim.model, sim.data)

    def finish():
        sim.policy.status = "succeeded"
        sim.policy.success = True
        sim.running = False

    monkeypatch.setattr(sim.policy, "update", finish)
    sim.step(10)
    assert not sim.policy.success or collision_issue(sim) is None
    assert sim.data.time == sim.model.opt.timestep
