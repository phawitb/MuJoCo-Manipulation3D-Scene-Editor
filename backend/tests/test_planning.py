import time
import numpy as np
import pytest
from backend.examples import example_scene
from backend.simulation import Simulation


def test_rehearsal_does_not_move_live_scene_and_matches_execution():
    from backend.planning import calculate_plan, physics_fingerprint

    sim = Simulation(example_scene())
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert plan["verified"], plan["message"]
    assert len(plan["points"]) > 30 and plan["duration"] > 10
    assert physics_fingerprint(sim) == before
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    for _ in range(1500):
        sim.step(10)
        if sim.policy.status in ("succeeded", "failed"):
            break
    assert sim.policy.success
    assert not sim.data.eq_active.any()
    np.testing.assert_allclose(
        sim.data.site("gripperframe").xpos, plan["points"][-1], atol=0.001
    )


def test_unreachable_rehearsal_is_explicit_and_non_mutating():
    from backend.planning import calculate_plan, physics_fingerprint

    scene = example_scene()
    scene.objects[0].position[0] = 2
    sim = Simulation(scene)
    before = physics_fingerprint(sim)
    plan = calculate_plan(sim)
    assert not plan["verified"] and plan["status"] == "failed"
    assert "reach" in plan["message"].lower()
    assert before == physics_fingerprint(sim)


def test_session_requires_calculation_and_invalidates_edits():
    from backend.sessions import Session, Command

    s = Session()
    s.execute(Command(type="example"))
    with pytest.raises(ValueError, match="[Cc]alculate"):
        s.execute(Command(type="run"))
    s.execute(Command(type="plan"))
    deadline = time.monotonic() + 30
    while s.packet()["plan"]["status"] == "calculating" and time.monotonic() < deadline:
        time.sleep(0.02)
    assert s.packet()["plan"]["verified"]
    s.execute(
        Command(
            type="camera",
            camera="front",
            value={"position": [1, -1, 1.3], "target": [0, 0, 0.8]},
        )
    )
    assert s.packet()["plan"]["verified"]
    s.execute(
        Command(
            type="object_update", id="spoon", patch={"position": [-0.09, -0.07, 0.756]}
        )
    )
    assert s.packet()["plan"]["status"] == "idle"
    with pytest.raises(ValueError, match="[Cc]alculate"):
        s.execute(Command(type="run"))


def test_inflight_plan_cannot_resurrect_after_edit_or_deletion():
    from backend.sessions import Session, Command

    s = Session()
    s.execute(Command(type="example"))
    s.execute(Command(type="plan"))
    s.execute(Command(type="object_remove", id="spoon"))
    time.sleep(0.1)
    assert s.packet()["plan"]["status"] == "idle"
    assert not s.packet()["plan"]["verified"]
