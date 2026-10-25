"""Servo-loop behavior under load, deadband, reversals and saturation."""

import math
import pytest
from backend.modules.connection.tracking import TrackingController


def run_plant(controller, target, seconds=12, load=0.06, dt=0.05):
    measured = list(controller.output)
    history = []
    for _ in range(round(seconds / dt)):
        command = controller.step(target, measured, dt, [math.tau / 4096] * 6)
        # Approximate position-servo lag under a constant load; independent of controller code.
        for i in range(6):
            equilibrium = command[i] + (load if i == 2 else 0)
            measured[i] += 0.4 * (equilibrium - measured[i])
        history.append((list(command), list(measured)))
    return measured, history


def test_loaded_elbow_converges_without_altering_requested_pose():
    c = TrackingController([0.0] * 6)
    desired = [0.0, 0.0, -0.1, 0.0, 0.0, 0.0]
    measured, history = run_plant(c, desired)
    assert abs(measured[2] - desired[2]) < 0.006
    assert c.reference == pytest.approx(desired)
    assert -0.08 < c.bias[2] < -0.04
    assert max(abs(q[2]) for _, q in history) < 0.15


def test_reversals_have_bounded_command_speed_and_acceleration():
    c = TrackingController([0.0] * 6)
    measured = [0.0] * 6
    prev = c.output.copy()
    velocity = [0.0] * 6
    for n in range(500):
        dt = 0.03 if n % 2 else 0.07
        desired = [0.18 if n < 150 else -0.18] * 6
        command = c.step(desired, measured, dt, [0.0015] * 6)
        speed = [(a - b) / dt for a, b in zip(command, prev)]
        assert max(abs(v) for v in speed) <= 0.3 + 1e-9
        assert max(abs(a - b) / dt for a, b in zip(speed, velocity)) <= 1.2 + 1e-9
        measured = list(command)
        prev, velocity = list(command), speed
    assert max(abs(q + 0.18) for q in measured) < 0.008


def test_bias_is_bounded_for_stalled_motor_and_clears_on_reset():
    c = TrackingController([0.0] * 6)
    for _ in range(2000):
        c.step([0.25] * 6, [0.0] * 6, 0.05, [0.0015] * 6)
        assert max(abs(b) for b in c.bias) <= 0.1
    c.reset([0.05] * 6)
    assert c.bias == [0.0] * 6 and c.velocity == [0.0] * 6
    assert c.output == [0.05] * 6


def test_preserved_load_bias_stages_a_stationary_hold():
    c = TrackingController([0.0] * 6)
    measured, _ = run_plant(c, [0.0] * 6)
    bias = c.bias.copy()
    c.reset(measured, preserve_bias=True)
    assert c.bias == bias
    assert c.output == pytest.approx([q + b for q, b in zip(measured, bias)])
    assert c.velocity == [0.0] * 6


@pytest.mark.parametrize("dt", [0, -0.1, 0.3, float("nan")])
def test_invalid_or_stale_cycle_does_not_accumulate_correction(dt):
    c = TrackingController([0.0] * 6)
    with pytest.raises(ValueError):
        c.step([0.1] * 6, [0.0] * 6, dt, [0.0015] * 6)
    assert c.bias == [0.0] * 6 and c.output == [0.0] * 6
