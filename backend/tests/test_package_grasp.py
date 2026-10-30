"""Physical regression for an imported antenna/housing object above a cup."""

import json
from pathlib import Path
import numpy as np
from backend.schema import Scene
from backend.simulation import Simulation
from backend.planning import calculate_plan


def test_imported_linktrack_rehearses_and_completes_without_changing_live_scene():
    scene = Scene.model_validate(
        json.loads(
            (Path(__file__).parent / "fixtures/linktrack-cup-scene.json").read_text()
        )
    )
    sim = Simulation(scene)
    before = sim.data.qpos.copy()
    result = calculate_plan(sim)
    assert result["verified"], result["message"]
    assert np.array_equal(sim.data.qpos, before)
    assert sim.data.time == 0
    assert result["configuration"]["transfer_clearance"] == 0.035
    sim.policy.configuration = result["configuration"]
    sim.start_policy()
    held = False
    max_height = sim.data.body("object_" + scene.task.source).xpos[2]
    start_height = max_height
    for _ in range(3000):
        sim.step(10)
        max_height = max(
            max_height, sim.data.body("object_" + scene.task.source).xpos[2]
        )
        held |= sim.policy.held
        assert not sim.data.eq_active.any()
        if sim.policy.held:
            assert sim.policy.contact["maxPenetration"] < 0.0015
        if sim.policy.status in ("failed", "succeeded"):
            break
    assert held and max_height > start_height + 0.06
    assert sim.policy.success, sim.policy.message
    assert sim.model.neq == Simulation(Scene()).model.neq
