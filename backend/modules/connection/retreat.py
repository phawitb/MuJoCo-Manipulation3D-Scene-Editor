"""A slow departure from an existing, shallow jaw/table overlap only.

This never turns contacts off: the complete path must monotonically separate
all initially overlapping pairs and introduce no other arm collision.
"""

import math
import time
import numpy as np
import mujoco
from ...safety import BODY_TOLERANCE


class TableRetreatGuard:
    def __init__(self, sim, q):
        if sim.scene.objects:
            raise ValueError(
                "Clear scene objects before a table retreat; verify the real workspace is clear"
            )
        self.sim = sim
        self.model = sim.model
        self.data = mujoco.MjData(self.model)
        self.data.qpos[:] = sim.data.qpos
        self.table = self.model.geom("table").id
        jaws = {self.model.body(n).id for n in ("gripper", "moving_jaw_so101_v1")}
        self.pairs = {
            tuple(sorted((self.table, g)))
            for g in range(self.model.ngeom)
            if self.model.geom_bodyid[g] in jaws and self.model.geom_contype[g]
        }
        self.initial = self.depths(q)
        deepest = min(self.initial.values(), default=0)
        if not -0.008 <= deepest < -BODY_TOLERANCE:
            raise ValueError("Retreat requires a jaw/table overlap of at most 8 mm")
        self.validate(q, self.initial)

    def depths(self, q):
        for v, (lo, hi) in zip(q, self.model.jnt_range[:6]):
            if not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError("Retreat joint limit exceeded")
        self.data.qpos[:6] = q
        mujoco.mj_fwdPosition(self.model, self.data)
        return {
            pair: min(
                0.0, mujoco.mj_geomDistance(self.model, self.data, *pair, 0.05, None)
            )
            for pair in self.pairs
        }

    def validate(self, q, previous):
        depths = self.depths(q)
        if any(depths[p] < previous[p] - BODY_TOLERANCE for p in self.pairs):
            raise ValueError("Retreat would deepen a table contact")
        for c in self.data.contact:
            pair = tuple(sorted(int(g) for g in c.geom))
            if c.dist < -BODY_TOLERANCE and pair not in self.pairs:
                raise ValueError("Retreat would create another collision")
        return {p: max(previous[p], depths[p]) for p in self.pairs}

    def path(self, start, target, *, require_clear=True):
        previous = self.initial
        for fraction in np.linspace(0, 1, 101):
            previous = self.validate(
                np.asarray(start) + fraction * (np.asarray(target) - start), previous
            )
        if require_clear and min(previous.values()) < -BODY_TOLERANCE:
            raise ValueError("Retreat does not clear the table")


def choose_retreat(guard, measured, held):
    # Prefer elbow flexion: never add shoulder effort to overcome an unknown
    # obstruction. Only move an axis already close to its held goal.
    guard.path(measured, held, require_clear=False)
    for joint, delta in ((2, -0.08), (1, -0.08)):
        if abs(held[joint] - measured[joint]) > 0.04:
            continue
        target = list(held)
        target[joint] += delta
        try:
            guard.path(measured, target)
            guard.path(held, target)
            # The departure must also work if unchanged axes remain where
            # measured, rather than assuming their servo errors disappear.
            actual_target = list(measured)
            actual_target[joint] += delta
            guard.path(measured, actual_target)
            return target
        except ValueError:
            continue
    raise ValueError("No separating retreat available from measured joint angles")


def retreat(service, session_id):
    from .tracking import TrackingController

    with service.lock:
        service._owner(session_id)
        service._calibrated()
        if service.enabled or service.sync_mode != "off" or service._preparing:
            raise ValueError("Stop motion before lifting clear")
        session = service.bridge.session()
        with session.lock:
            if session.sim.running:
                raise ValueError("Pause Gym before lifting clear")
            q = service._read()
            if not all(r["torque"] and "goal_raw" in r for r in service.telemetry):
                raise ValueError(
                    "Retreat requires fresh held servo goals and torque already on"
                )
            held = [
                service._angle(i, row["goal_raw"])
                for i, row in enumerate(service.telemetry)
            ]
            if max(abs(a - b) for a, b in zip(held, q)) > TrackingController.MAX_BIAS:
                raise ValueError("Existing hold differs too far from measured pose")
            guard = TableRetreatGuard(session.sim, q)
            target = choose_retreat(guard, q, held)
            joint = next(i for i in range(6) if target[i] != held[i])
            budgets = [max(0.04, abs(a - b) + 0.003) for a, b in zip(held, q)]
            service._raw(target)
            model = session.sim.model
        service.recovering = True
        service.enabled = True
        service.target_rad = held
        service.lease_until = time.monotonic() + 3
        service.fault = None
    started = time.monotonic()
    previous = guard.initial
    command = list(held)
    try:
        while time.monotonic() - started < 12:
            with service.lock, session.lock:
                if not service.recovering or time.monotonic() > service.lease_until:
                    raise ValueError(
                        "Table retreat stopped or controller heartbeat expired"
                    )
                if session.sim.model is not model or session.sim.running:
                    raise ValueError("Scene changed during table retreat")
                measured = service._read()
                previous = guard.validate(measured, previous)
                for i, (a, b, limit) in enumerate(zip(command, measured, budgets)):
                    if abs(a - b) > limit:
                        name = service.calibration.joints[i].name
                        raise ValueError(
                            f"Retreat tracking error: {name} differs by "
                            f"{math.degrees(abs(a - b)):.2f} degrees; motion stopped"
                        )
                next_command = list(command)
                next_command[joint] = max(
                    target[joint], held[joint] - 0.025 * (time.monotonic() - started)
                )
                guard.validate(next_command, guard.initial)
                service.driver.goals(service._raw(next_command))
                command = service.target_rad = next_command
                if command[joint] <= target[joint] and abs(command[joint] - measured[joint]) < 0.04:
                    service.bridge.validate(measured, measured)
                    # Retain the existing gravity-compensated goal, not a new
                    # uncompensated encoder hold that makes the arm sag again.
                    service.tracker = TrackingController(
                        measured, limits=service._control_limits()
                    )
                    service.tracker.bias = [a - b for a, b in zip(command, measured)]
                    service.tracker.output = list(command)
                    service.desired_rad = measured
                    service.enabled = service.recovering = False
                    service.bridge.set(measured)
                    session.broadcast(session.packet())
                    return service.status()
            time.sleep(0.05)
        raise ValueError("Table retreat did not settle in time")
    except Exception as exc:
        with service.lock:
            service.recovering = False
            service._fault(str(exc), hold=False)
        raise
