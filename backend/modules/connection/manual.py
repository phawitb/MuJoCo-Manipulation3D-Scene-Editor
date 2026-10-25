"""Replaceable manual targets with measured feedback and non-deepening departure."""

import math
import time
import mujoco
import numpy as np
from .tracking import TrackingController
from ...safety import SELF_TOLERANCE, BODY_TOLERANCE


class MotionGuard:
    def __init__(self, sim, q):
        self.sim, self.model = sim, sim.model
        self.data = mujoco.MjData(self.model)
        self.data.qpos[:] = sim.data.qpos
        self.robot = set(range(1, self.model.nbody)) - set(sim.object_bodies.values())
        self.previous = self.depths(q)
        if min(self.previous.values(), default=0) < -0.008:
            raise ValueError(
                "Starting overlap exceeds 8 mm; reposition the arm before manual motion"
            )

    def validate_angles(self, q):
        if len(q) != 6 or not all(math.isfinite(v) for v in q):
            raise ValueError("Six finite angles required")
        if any(not lo <= v <= hi for v, (lo, hi) in zip(q, self.model.jnt_range[:6])):
            raise ValueError("Manual target exceeds robot joint limits")

    def depths(self, q):
        self.validate_angles(q)
        self.data.qpos[:6] = q
        mujoco.mj_fwdPosition(self.model, self.data)
        depths = {}
        for c in self.data.contact:
            a, b = (int(self.model.geom_bodyid[g]) for g in c.geom)
            if a not in self.robot and b not in self.robot:
                continue
            pair = tuple(sorted(int(g) for g in c.geom))
            depths[pair] = min(depths.get(pair, 0), float(c.dist))
        return depths

    def check(self, q, previous):
        depths = self.depths(q)
        for pair in depths.keys() | previous.keys():
            a, b = (int(self.model.geom_bodyid[g]) for g in pair)
            tolerance = (
                SELF_TOLERANCE
                if a in self.robot and b in self.robot
                else BODY_TOLERANCE
            )
            if depths.get(pair, 0) < previous.get(pair, 0) - tolerance:
                raise ValueError("Manual path creates or deepens a collision")
        return {p: max(previous.get(p, 0), depths.get(p, 0)) for p in previous}

    def path(self, start, target):
        previous = self.previous.copy()
        count = max(1, math.ceil(max(abs(a - b) for a, b in zip(start, target)) / 0.01))
        for f in np.linspace(0, 1, count + 1):
            previous = self.check(
                np.asarray(start) + f * (np.asarray(target) - start), previous
            )

    def observe(self, q):
        self.previous = self.check(q, self.previous)


class ManualMotion:
    def __init__(self, service, session, measured, target, guard=None):
        self.service, self.session = service, session
        self.guard = guard or MotionGuard(session.sim, measured)
        self.guard.path(measured, target)
        self.target = list(target)
        self.tracker = TrackingController(measured, limits=service._control_limits())
        if all("goal_raw" in row for row in service.telemetry):
            held = [
                service._angle(i, row["goal_raw"])
                for i, row in enumerate(service.telemetry)
            ]
            if max(abs(a - b) for a, b in zip(held, measured)) > self.tracker.MAX_BIAS:
                raise ValueError(
                    "Existing servo hold differs too far from measured pose"
                )
            self.guard.path(measured, held)
            self.tracker.bias = [a - b for a, b in zip(held, measured)]
            self.tracker.output = held
        self.tracker.REFERENCE_SPEED = 0.24
        self.tracker.MAX_SPEED = 0.8
        self.tracker.MAX_ACCELERATION = 2.4
        self.last = time.monotonic()
        self.progress_at = self.last
        self.progress_pose = list(measured)
        self.settled = 0
        self.phase = "moving"

    def replace(self, measured, target):
        self.guard.path(measured, target)
        self.target = list(target)
        self.settled = 0
        self.phase = "moving"

    def tick(self, measured):
        s = self.service
        with self.session.lock:
            if (
                self.session.closed
                or self.session.sim.model is not self.guard.model
                or self.session.sim.running
            ):
                raise ValueError("Scene changed during manual control")
            self.guard.observe(measured)
            now = time.monotonic()
            if max(abs(a - b) for a, b in zip(measured, self.progress_pose)) > 0.004:
                self.progress_at, self.progress_pose = now, list(measured)
            # Closed jaws have a mechanical stop; keep its residual visible in UI.
            tolerances = [math.radians(1)] * 5 + [math.radians(1.5)]
            reached = all(
                abs(a - b) <= tolerance
                for a, b, tolerance in zip(measured, self.target, tolerances)
            )
            stationary = max(abs(v) for v in self.tracker.velocity) < 0.02
            arrived = (
                max(abs(a - b) for a, b in zip(self.tracker.reference, self.target))
                < 0.003
            )
            self.settled = self.settled + 1 if reached and stationary and arrived else 0
            self.phase = "holding" if self.settled >= 6 else "moving"
            if reached:
                self.progress_at = now
            if now - self.progress_at > 6:
                raise ValueError(
                    "Manual movement stalled; stopped at measured feedback"
                )
            dt = max(0.001, now - self.last)
            # Keep the reference on the checked joint-space segment. Independent
            # axis ramps would reach short-axis goals early and cut another path.
            delta = np.asarray(self.target) - self.tracker.reference
            distance = float(np.max(np.abs(delta)))
            fraction = min(
                1.0, self.tracker.REFERENCE_SPEED * dt / max(distance, 1e-12)
            )
            reference = np.asarray(self.tracker.reference) + fraction * delta
            target = self.tracker.step(
                reference.tolist(),
                measured,
                dt,
                [c.radians_per_tick for c in s.calibration.joints],
            )
            if max(abs(a - b) for a, b in zip(measured, target)) > 0.15:
                raise ValueError("Manual tracking error exceeds 0.15 radians")
            raw = s._raw(target)
            target = [s._angle(i, v) for i, v in enumerate(raw)]
            self.guard.path(measured, target)
            if time.monotonic() - s.measured_at > 0.2:
                raise ValueError("Stale feedback after manual path validation")
            s.driver.goals(raw)
            s.target_rad = target
            s.desired_rad = list(self.target)
            s.tracker = self.tracker
            self.last = now
