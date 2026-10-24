"""A rim approach needs clearance on both sides, not only a wider moving jaw."""

import mujoco
import numpy as np
import pytest
from backend.examples import example_scene
from backend.simulation import Simulation
from backend.planning import calculate_plan


def start_cup(example="kalas-rim-to-plate", configuration=None):
    sim = Simulation(example_scene(example))
    sim.policy.configuration = configuration or {"rim_angle": -np.pi / 2}
    sim.start_policy()
    return sim


def advance_to(sim, phase):
    for _ in range(2500):
        sim.step(1)
        assert sim.policy.status != "failed", sim.policy.message
        if sim.policy.phase == phase:
            return
    raise AssertionError(f"Never reached {phase}")


@pytest.fixture(scope="module")
def verified_configurations():
    result = {}
    for example in ("kalas-rim-to-plate", "kalas-loaded-cup-to-plate"):
        plan = calculate_plan(Simulation(example_scene(example)))
        assert plan["verified"], plan["message"]
        result[example] = plan["configuration"]
    return result


@pytest.mark.parametrize("example", ["kalas-rim-to-plate", "kalas-loaded-cup-to-plate"])
def test_open_approach_clears_both_sides_of_the_cup_rim(
    example, verified_configurations
):
    sim = start_cup(example, verified_configurations[example])
    # Approach and descend take longer than the helper's single-phase timeout.
    advance_to(sim, "Approach")
    advance_to(sim, "Descend")
    advance_to(sim, "Grasp")
    cup = sim.object_bodies["cup"]
    m, d = sim.model, sim.data
    for jaw in ["gripper", "moving_jaw_so101_v1"]:
        fingers = [
            g
            for g in range(m.ngeom)
            if m.geom_bodyid[g] == m.body(jaw).id and m.geom_contype[g]
        ]
        shell = [
            g for g in range(m.ngeom) if m.geom_bodyid[g] == cup and m.geom_contype[g]
        ]
        distance = min(
            mujoco.mj_geomDistance(m, d, a, b, 0.1, None)
            for a in fingers
            for b in shell
        )
        assert distance >= 0.006, (jaw, distance)


@pytest.mark.parametrize("example", ["kalas-rim-to-plate", "kalas-loaded-cup-to-plate"])
@pytest.mark.parametrize("dx,dy", [(0.002, 0), (-0.002, 0), (0, 0.002), (0, -0.002)])
def test_fixed_approach_tolerates_small_cup_position_errors(
    example, dx, dy, verified_configurations
):
    sim = start_cup(example, verified_configurations[example])
    advance_to(sim, "Approach")
    # Fault injection only: perturb the real cup/cargo AFTER the grasp waypoints
    # were calculated. The controller receives no corrected target or replan.
    for oid in ["cup"] + sim.policy.contents:
        bid = sim.object_bodies[oid]
        adr = sim.model.jnt_qposadr[sim.model.body_jntadr[bid]]
        sim.data.qpos[adr : adr + 2] += [dx, dy]
    mujoco.mj_forward(sim.model, sim.data)
    for _ in range(3000):
        sim.step(10)
        assert not sim.data.eq_active.any()
        if sim.policy.status in ("failed", "succeeded"):
            break
    assert sim.policy.success, sim.policy.message


def test_tight_candidate_stops_before_closing_even_if_it_could_grasp():
    sim = start_cup(configuration={"rim_angle": np.pi / 4})
    advance_to(sim, "Approach")
    advance_to(sim, "Descend")
    for _ in range(2000):
        sim.step(1)
        if sim.policy.status == "failed":
            break
    assert sim.policy.status == "failed"
    assert "at least 4 mm" in sim.policy.message
    assert not sim.policy.held
    assert sim.data.ctrl[5] > 0, (
        "The jaws must remain open when clearance is insufficient"
    )
