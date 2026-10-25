import numpy as np
from backend.simulation import Simulation
from backend.modules.connection.manual import MotionGuard

Q = [-0.10047574, -1.71268955, 1.68967984, 0.87283507, -0.03911651, 0.02761165]


def test_manual_guard_preserves_shallow_contact_without_allowing_deeper_motion():
    sim = Simulation()
    guard = MotionGuard(sim, Q)
    target = list(Q)
    target[4] += 0.03
    guard.path(Q, target)
    found_rejection = False
    for j in [1, 2, 3]:
        for delta in [-0.03, 0.03]:
            candidate = list(Q)
            candidate[j] += delta
            try:
                guard.path(Q, candidate)
            except ValueError:
                found_rejection = True
    assert found_rejection


def test_preview_guard_never_changes_live_simulation():
    sim = Simulation()
    before = sim.data.qpos.copy()
    guard = MotionGuard(sim, Q)
    guard.path(Q, Q)
    assert np.array_equal(sim.data.qpos, before)
