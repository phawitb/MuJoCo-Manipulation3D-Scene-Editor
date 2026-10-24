"""A utensil must start supported inside a cup and be physically extracted."""

import numpy as np
from backend.examples import example_scene
from backend.simulation import Simulation
from backend.planning import calculate_plan


def test_cup_to_plate_starts_supported_and_executes_without_attachment():
    sim = Simulation(example_scene("kalas-cup-to-plate"))
    sim.step(1000)
    spoon = sim.data.body("object_spoon")
    cup = sim.data.body("object_source_cup")
    assert abs(spoon.xmat.reshape(3, 3)[2, 0]) > 0.7
    assert np.linalg.norm(spoon.xpos[:2] - cup.xpos[:2]) < 0.06
    bodies = {spoon.id, cup.id}
    assert any(
        {int(sim.model.geom_bodyid[c.geom[0]]), int(sim.model.geom_bodyid[c.geom[1]])}
        == bodies
        for c in sim.data.contact
    )
    plan = calculate_plan(sim)
    assert plan["verified"], plan["message"]
    sim.policy.configuration = plan["configuration"]
    sim.start_policy()
    lifted = False
    cleared = False
    cup_origin = cup.xpos.copy()
    for _ in range(3000):
        sim.step(10)
        assert not sim.data.eq_active.any()
        assert np.linalg.norm(cup.xpos - cup_origin) < 0.02
        assert cup.xmat.reshape(3, 3)[2, 2] > 0.97
        if sim.policy.phase == "Transfer" and not cleared:
            spoon_bottom = spoon.xpos[2] - np.abs(
                spoon.xmat.reshape(3, 3)[2]
            ) @ np.array([0.08, 0.0165, 0.004])
            assert spoon_bottom > cup.xpos[2] + 0.0405 + 0.002
            cleared = True
        lifted |= sim.policy.held and sim.data.body("object_spoon").xpos[2] > 0.90
        if sim.policy.status in ("failed", "succeeded"):
            break
    assert cleared and lifted and sim.policy.success, sim.policy.packet()
