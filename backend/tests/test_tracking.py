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


@pytest.mark.parametrize("lag", [0.10, 0.22])
def test_repeated_direction_changes_track_a_loaded_lagging_servo(lag):
    controller = TrackingController([0.0] * 6)
    measured = [0.0] * 6
    errors = []
    elapsed = 0.0
    for n in range(1000):
        dt = 0.04 if n % 2 else 0.06
        elapsed += dt
        desired = [0.18 * math.sin(0.8 * elapsed) if elapsed < 40 else 0.0] * 6
        command = controller.step(desired, measured, dt, [math.tau / 4096] * 6)
        # First-order servo response with constant elbow gravity load. The
        # plant is independent of the controller and runs with variable timing.
        for i in range(6):
            equilibrium = command[i] + (0.06 if i == 2 else 0.0)
            measured[i] += (1 - math.exp(-dt / lag)) * (equilibrium - measured[i])
        if 8 < elapsed < 38:
            errors.append(measured[2] - desired[2])
    assert math.sqrt(sum(error**2 for error in errors) / len(errors)) < 0.005
    assert max(abs(q) for q in measured) < 0.006


@pytest.mark.parametrize("sign", [-1, 1])
def test_compensation_brakes_inside_joint_limits_without_windup(sign):
    c = TrackingController([0.0] * 6, limits=[(-0.3, 0.3)] * 6)
    measured = [0.0] * 6
    previous = c.output.copy()
    velocity = [0.0] * 6
    for n in range(600):
        dt = [0.03, 0.07, 0.15][n % 3]
        desired = [sign * (0.299 if n < 350 else -0.299)] * 6
        output = c.step(desired, measured, dt, [0.0015] * 6)
        speed = [(a - b) / dt for a, b in zip(output, previous)]
        assert all(-0.3 <= q <= 0.3 for q in output)
        assert max(abs(v) for v in speed) <= 0.3 + 1e-9
        assert max(abs(a - b) / dt for a, b in zip(speed, velocity)) <= 1.2 + 1e-9
        measured = [q - sign * 0.008 for q in output]
        previous, velocity = output, speed
    assert abs(output[0] + sign * 0.299) < 0.02


def test_invalid_desired_pose_is_rejected_not_clamped():
    c = TrackingController([0.0] * 6, limits=[(-0.3, 0.3)] * 6)
    with pytest.raises(ValueError, match="target.*limit"):
        c.step([0.4] * 6, [0.0] * 6, 0.05, [0.0015] * 6)
    assert c.output == [0.0] * 6


def test_mujoco_compliant_limit_is_projected_only_within_physics_tolerance():
    from backend.modules.connection.bridge import hardware_target

    assert hardware_target([1.0005] * 6, [(-1, 1)] * 6) == [1] * 6
    assert hardware_target([-1.0005] * 6, [(-1, 1)] * 6) == [-1] * 6
    with pytest.raises(ValueError, match="Simulation joint limit"):
        hardware_target([1.003] * 6, [(-1, 1)] * 6)
