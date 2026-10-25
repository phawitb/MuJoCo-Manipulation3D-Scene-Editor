"""Explicit, slow inward recovery for encoder-scale range violations.

Normal motion still requires strict joint/calibration limits. Only this mode
accepts a starting violation up to 0.5 degrees, moves at most two axes by at
most 1.5 degrees, one at a time, with whole-arm checks at each half tick.
"""

import math
import time
from .manual import MotionGuard


class RecoveryGuard(MotionGuard):
    def __init__(self, sim, start, target, ticks):
        self.envelope = [
            (
                max(min(a, b) - tick, a - math.radians(1.5)),
                min(max(a, b) + tick, a + math.radians(1.5)),
            )
            for a, b, tick in zip(start, target, ticks)
        ]
        super().__init__(sim, start)

    def validate_angles(self, q):
        if len(q) != 6 or any(
            not math.isfinite(v) or not lo <= v <= hi
            for v, (lo, hi) in zip(q, self.envelope)
        ):
            raise ValueError("Arm moved outside the bounded recovery path")


def recovery_target(service, measured, deadbands):
    if len(deadbands) != 6 or any(
        not isinstance(v, int) or not 0 <= v <= 255 for v in deadbands
    ):
        raise ValueError("Valid servo deadband readings required for recovery")
    target = list(measured)
    changed = []
    for i, (value, (lo, hi), c) in enumerate(
        zip(measured, service._control_limits(), service.calibration.joints)
    ):
        if lo <= value <= hi:
            continue
        excess = max(lo - value, value - hi)
        if excess > math.radians(0.5):
            raise ValueError(
                f"{c.name} is more than 0.5 degrees outside its range; reposition or review calibration"
            )
        # Exceed the actual servo deadband without editing EEPROM. Both the
        # inward margin and total travel are checked after encoder quantization.
        target[i] = (
            max(
                lo + 4 * c.radians_per_tick,
                value + (deadbands[i] + 4) * c.radians_per_tick,
            )
            if value < lo
            else min(
                hi - 4 * c.radians_per_tick,
                value - (deadbands[i] + 4) * c.radians_per_tick,
            )
        )
        changed.append(i)
    if not 1 <= len(changed) <= 2:
        raise ValueError(
            "Recovery requires one or two joints slightly outside their range"
        )
    raw = service._raw(target)
    target = [service._angle(i, v) for i, v in enumerate(raw)]
    if any(
        not lo <= v <= hi or abs(v - start) > math.radians(1.5)
        for v, start, (lo, hi) in zip(target, measured, service._control_limits())
    ):
        raise ValueError("No bounded recovery target inside the calibrated joint range")
    return target, raw, changed


def check_recovery_path(guard, service, start_raw, target_raw, joint):
    steps = abs(target_raw[joint] - start_raw[joint]) * 2
    if not 0 < steps <= 128:
        raise ValueError("Recovery path is too large to verify")
    previous = guard.previous.copy()
    for step in range(steps + 1):
        raw = list(start_raw)
        raw[joint] += (target_raw[joint] - raw[joint]) * step / steps
        q = [service._angle(i, v) for i, v in enumerate(raw)]
        previous = guard.check(q, previous)


def choose_stage(guard, service, measured_raw, target_raw, pending):
    for joint in pending:
        command = list(measured_raw)
        command[joint] = target_raw[joint]
        try:
            check_recovery_path(guard, service, measured_raw, command, joint)
            return joint, command
        except ValueError:
            continue
    raise ValueError(
        "No collision-safe inward recovery from measured pose; reposition the arm"
    )


def recover_limits(service, session_id, control_epoch):
    s = service
    with s.lock:
        s._owner(session_id)
        s._calibrated()
        if control_epoch != s.control_epoch:
            raise ValueError(
                "Recovery command expired after Stop or a connection change"
            )
        if (
            s.enabled
            or s.recovering
            or s.manual
            or s._preparing
            or s.execution.active
            or s.sync_mode != "off"
        ):
            raise ValueError("Stop active motion before recovering joint limits")
        session = s.bridge.session()
        with session.lock:
            if session.closed or session.sim.running:
                raise ValueError("Pause Gym before recovering joint limits")
            measured = s._read()
            start_raw = [r["raw"] for r in s.telemetry]
            if not all(
                r["torque"] and "goal_raw" in r and abs(r["goal_raw"] - r["raw"]) <= 1
                for r in s.telemetry
            ):
                raise ValueError(
                    "Recovery requires Torque On holding the measured position"
                )
            deadbands = s.driver.position_deadbands()
            target, raw, pending = recovery_target(s, measured, deadbands)
            guard = RecoveryGuard(
                session.sim,
                measured,
                target,
                [c.radians_per_tick for c in s.calibration.joints],
            )
            joint, command = choose_stage(guard, s, start_raw, raw, pending)
            s._read()
            if [r["raw"] for r in s.telemetry] != start_raw or not all(
                r["torque"] and "goal_raw" in r and abs(r["goal_raw"] - r["raw"]) <= 1
                for r in s.telemetry
            ):
                raise ValueError(
                    "Arm moved during recovery validation; retry from a stationary hold"
                )
            s.control_epoch += 1
            recovery_epoch = s.control_epoch
            s.enabled = s.recovering = s.limit_recovery_active = True
            s.target_rad = s.desired_rad = [
                s._angle(i, v) for i, v in enumerate(command)
            ]
            s.tracker = None
            s.lease_until = time.monotonic() + 3
            s.fault = None
            # Mark active before any write so partial bus failures also stop.
            try:
                s.driver.goals(start_raw)
                s.driver.torque([195] * 6)
                s.driver.goals(command)
            except Exception as exc:
                s._fault(str(exc))
                raise
    started = time.monotonic()
    holding, stationary_since = False, None
    previous_raw = start_raw
    try:
        while time.monotonic() - started < 6:
            with s.lock, session.lock:
                if (
                    s.control_epoch != recovery_epoch
                    or not s.limit_recovery_active
                    or time.monotonic() > s.lease_until
                ):
                    raise ValueError("Recovery stopped or controller heartbeat expired")
                if (
                    session.closed
                    or session.sim.model is not guard.model
                    or session.sim.running
                ):
                    raise ValueError("Scene changed during joint recovery")
                measured = s._read()
                if not all(r["torque"] for r in s.telemetry):
                    raise ValueError("Motor torque changed during joint recovery")
                guard.observe(measured)
                measured_raw = [r["raw"] for r in s.telemetry]
                # Only the selected axis may move; hold the other axes exactly
                # where they were measured, including any still outside limits.
                if any(
                    abs(v - command[i]) > 1
                    for i, v in enumerate(measured_raw)
                    if i != joint
                ):
                    raise ValueError("Another joint moved during single-axis recovery")
                lo, hi = s._control_limits()[joint]
                inside = lo <= measured[joint] <= hi
                reached = (
                    abs(measured_raw[joint] - command[joint]) <= deadbands[joint] + 1
                )
                stationary = measured_raw == previous_raw and all(
                    r.get("moving") is False and r.get("present_speed_raw") == 0
                    for r in s.telemetry
                )
                previous_raw = measured_raw
                if not holding and inside and reached:
                    # Issue a measured hold, then require fresh stationary
                    # feedback for 250 ms before any next-axis command. Small
                    # 0/1 tick steps at this speed do not mean motion stopped.
                    s.driver.goals(measured_raw)
                    s.target_rad = s.desired_rad = list(measured)
                    command = measured_raw
                    holding, stationary_since = True, None
                elif holding:
                    if not inside or any(
                        abs(a - b) > 1 for a, b in zip(command, measured_raw)
                    ):
                        raise ValueError(
                            "Measured hold did not settle inside recovery limits"
                        )
                    if not stationary:
                        stationary_since = None
                    elif stationary_since is None:
                        stationary_since = time.monotonic()
                    if (
                        stationary_since is not None
                        and time.monotonic() - stationary_since >= 0.25
                    ):
                        pending.remove(joint)
                        if not pending:
                            if not all(
                                lo <= v <= hi
                                for v, (lo, hi) in zip(measured, s._control_limits())
                            ):
                                raise ValueError(
                                    "Joint drifted outside limits during recovery"
                                )
                            s.enabled = s.recovering = s.limit_recovery_active = False
                            return s.status()
                        joint, command = choose_stage(
                            guard, s, measured_raw, raw, pending
                        )
                        if time.monotonic() - s.measured_at > 0.2:
                            raise ValueError(
                                "Stale feedback after recovery path validation"
                            )
                        s.driver.goals(command)
                        s.target_rad = s.desired_rad = [
                            s._angle(i, v) for i, v in enumerate(command)
                        ]
                        started = time.monotonic()
                        holding, stationary_since = False, None
            time.sleep(0.05)
        raise ValueError("Joint recovery did not settle; holding measured position")
    except Exception as exc:
        with s.lock:
            if s.limit_recovery_active and s.control_epoch == recovery_epoch:
                s._fault(str(exc))
        raise
