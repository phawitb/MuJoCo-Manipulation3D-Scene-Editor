"""Manual controls share the service's single hardware owner and lock."""

import math
import time
from .manual import ManualMotion


def _move(service, session_id, joints=None, preset=None):
    s = service
    with s.lock:
        s._owner(session_id)
        s._calibrated()
        if s._preparing or s.execution.active or s.sync_mode != "off" or s.recovering:
            raise ValueError(
                "Stop the current task or synchronization before manual control"
            )
        session = s.bridge.session()
        with session.lock:
            if session.sim.running:
                raise ValueError("Pause simulation before manual control")
            q = s._read()
            if not all(row["torque"] for row in s.telemetry):
                raise ValueError("Turn Torque On before moving the robot")
            if preset == "home":
                joints = list(session.sim.scene.robot.reset_joints)
            elif preset == "gym":
                joints = s.bridge.get()
            if (
                joints is None
                or len(joints) != 6
                or not all(math.isfinite(v) for v in joints)
            ):
                raise ValueError("Six finite target angles required")
            s._raw(q)
            s._raw(joints)
            # Cartesian controllers retain a tool-space arrival goal; a joint
            # command must replace that controller rather than only its target.
            if type(s.manual) is ManualMotion:
                s.manual.replace(q, joints)
            else:
                motion = ManualMotion(s, session, q, joints)
                if time.monotonic() - s.measured_at > 0.2:
                    raise ValueError("Stale feedback after manual path validation")
                s.driver.goals(s._raw(motion.tracker.output))
                s.driver.torque(
                    [
                        max(1, math.floor(0.8 / c.radians_per_tick))
                        for c in s.calibration.joints
                    ]
                )
                s.manual = motion
                s.target_rad = list(motion.tracker.output)
                s.tracker = motion.tracker
            s.desired_rad = list(joints)
            s.enabled = True
            s.lease_until = time.monotonic() + 3
            s.fault = None
            return s.status()


def _torque(service, session_id, enabled):
    s = service
    with s.lock:
        s._owner(session_id)
        if enabled:
            s._calibrated()
            if s._preparing or s.enabled or s.sync_mode != "off":
                raise ValueError("Stop motion before enabling torque")
            q = s._read()
            # Torque On is a stationary hold, not a motion target. Seed every
            # servo with its freshly read integer encoder before enabling it.
            # A manually positioned arm can be outside the calibrated motion
            # envelope; never clamp it to that envelope (which would move it).
            # Subsequent moves still pass _raw() and whole-arm path validation.
            s.driver.goals([row["raw"] for row in s.telemetry])
            s.driver.torque(
                [
                    max(1, math.floor(0.8 / c.radians_per_tick))
                    for c in s.calibration.joints
                ]
            )
            s.target_rad = list(q)
            s.desired_rad = list(q)
            s.tracker = None
            s.fault = None
        else:
            s._fault("Torque off; support the arm before releasing it", hold=False)
            s.driver.torque_off()
            s.target_rad = s.desired_rad = None
        s._read()
        if any(bool(row["torque"]) != enabled for row in s.telemetry):
            raise ValueError("Torque state could not be confirmed on every motor")
        return s.status()


def move(service, session_id, joints=None, preset=None, control_epoch=None):
    with service.lock:
        service._owner(session_id)
        if control_epoch is not None and control_epoch != service.control_epoch:
            raise ValueError("Manual command expired after Stop or a connection change")
        try:
            return _move(service, session_id, joints, preset)
        except Exception as exc:
            # A rejected replacement must not leave an older target moving.
            if service.manual is not None or isinstance(exc, OSError):
                service._fault(str(exc))
            raise


def torque(service, session_id, enabled, control_epoch=None):
    with service.lock:
        service._owner(session_id)
        if (
            enabled
            and control_epoch is not None
            and control_epoch != service.control_epoch
        ):
            raise ValueError("Torque command expired after Stop or a connection change")
        try:
            return _torque(service, session_id, enabled)
        except (OSError, RuntimeError) as exc:
            # Do not re-enable partially released motors after a bus fault.
            service._fault(str(exc), hold=False)
            raise
