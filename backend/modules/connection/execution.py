"""Independent real-arm task-space execution against a rehearsed scene estimate."""

import math
import time
from types import SimpleNamespace
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation
from .cartesian import CartesianMotion, ToolKinematics
from .episode_report import EpisodeReport
from ...planning import clone_simulation
from ...safety import collision_issue


class TaskGuard:
    """Check all arm links and planned carried objects; never ignore source solids."""

    def __init__(self, sim, reference=None, previous=None):
        self.sim, self.model = sim, sim.model
        self.data = mujoco.MjData(sim.model)
        self.data.qpos[:] = sim.data.qpos
        self.carried = []
        self.transition = None
        if previous is not None and reference is not None:
            r0 = Rotation.from_quat(previous["quaternion"])

            def vector(pose):
                return np.r_[
                    np.asarray(pose["position"]) - previous["position"],
                    0.07
                    * (Rotation.from_quat(pose["quaternion"]) * r0.inv()).as_rotvec(),
                    0.03 * (pose["opening_rad"] - previous["opening_rad"]),
                ]

            delta = vector(reference)
            if np.dot(delta, delta) > 1e-12:
                self.transition = (
                    np.asarray(previous["object_qpos"]),
                    sim.data.qpos[6:].copy(),
                    delta,
                    vector,
                )
        self.kinematics = ToolKinematics(sim)
        if sim.policy.held and reference is not None:
            rotation = Rotation.from_quat(reference["quaternion"])
            origin = np.asarray(reference["position"])
            ids = {sim.scene.task.source, *sim.policy.contents}
            for oid in ids:
                if oid not in sim.object_bodies:
                    continue
                body = self.model.body(sim.object_bodies[oid])
                adr = int(self.model.jnt_qposadr[body.jntadr[0]])
                pose = self.data.qpos[adr : adr + 7]
                local_position = rotation.inv().apply(pose[:3] - origin)
                local_rotation = rotation.inv() * Rotation.from_quat(
                    np.roll(pose[3:7], -1)
                )
                self.carried.append((adr, local_position, local_rotation))

    def observe(self, q):
        self.data.qpos[:6] = q
        if (
            len(q) != 6
            or not np.isfinite(q).all()
            or any(
                not lo <= v <= hi for v, (lo, hi) in zip(q, self.model.jnt_range[:6])
            )
        ):
            raise ValueError("Task joint limit exceeded")
        if self.transition is not None:
            start, end, delta, vector = self.transition
            progress = vector(self.kinematics.pose(q))
            fraction = float(
                np.clip(np.dot(progress, delta) / np.dot(delta, delta), 0, 1)
            )
            for offset in range(0, len(start), 7):
                self.data.qpos[6 + offset : 9 + offset] = start[
                    offset : offset + 3
                ] + fraction * (end[offset : offset + 3] - start[offset : offset + 3])
                a = Rotation.from_quat(np.roll(start[offset + 3 : offset + 7], -1))
                b = Rotation.from_quat(np.roll(end[offset + 3 : offset + 7], -1))
                rotation = (
                    Rotation.from_rotvec(fraction * (b * a.inv()).as_rotvec()) * a
                )
                self.data.qpos[9 + offset : 13 + offset] = np.roll(
                    rotation.as_quat(), 1
                )
        if self.carried:
            tool = self.kinematics.pose(q)
            rotation = Rotation.from_quat(tool["quaternion"])
            for adr, position, relative in self.carried:
                self.data.qpos[adr : adr + 3] = np.asarray(
                    tool["position"]
                ) + rotation.apply(position)
                self.data.qpos[adr + 3 : adr + 7] = np.roll(
                    (rotation * relative).as_quat(), 1
                )
        mujoco.mj_fwdPosition(self.model, self.data)
        issue = collision_issue(self.sim, self.data)
        if issue:
            raise ValueError("Whole-arm collision: " + issue)

    def path(self, start, target):
        count = max(1, math.ceil(max(abs(a - b) for a, b in zip(start, target)) / 0.01))
        for f in np.linspace(0, 1, count + 1):
            self.observe(np.asarray(start) + f * (np.asarray(target) - start))


class CartesianExecution:
    def __init__(self, service):
        self.service = service
        self.session = None
        self.phase = "idle"
        self.message = ""
        self.report = None
        self._report = None
        self.index = 0
        self.waypoints = []
        self.world = None

    @property
    def active(self):
        return self.session is not None

    def status(self):
        return dict(
            phase=self.phase,
            message=self.message,
            session_id=self.session.id if self.session else None,
            report=self.report,
            measurement_source="encoder_fk",
            object_verified=False,
            waypoint=self.index,
            total_waypoints=len(self.waypoints),
        )

    def start(self, session, trial, waypoints):
        s = self.service
        if not waypoints:
            raise ValueError("Rehearsal has no tool-space waypoints; calculate again")
        q = s._read()
        s._raw(q)
        TaskGuard(trial).observe(q)
        if not all(row["torque"] for row in s.telemetry):
            raise ValueError("Turn Torque On before Run Realrobot")
        self.world = SimpleNamespace(
            sim=clone_simulation(trial), lock=session.lock, closed=False
        )
        self.waypoints = waypoints
        self.index = 0
        motion = self._motion(q)
        if time.monotonic() - s.measured_at > 0.2:
            raise ValueError("Stale feedback after task path validation; retry")
        self.session = session
        self._report = EpisodeReport(session.id)
        self.report = None
        self._report.observe(motion.error)
        self.phase = "running"
        self.message = "Following tool goals from measured feedback. Object state is a scene estimate."
        try:
            s.enabled = True
            s.driver.goals(s._raw(motion.tracker.output))
            s.driver.torque(
                [
                    max(1, math.floor(0.8 / c.radians_per_tick))
                    for c in s.calibration.joints
                ]
            )
            s.manual = motion
            s.tracker = motion.tracker
            s.target_rad = list(motion.tracker.output)
            s.desired_rad = list(motion.target)
            s.sync_mode = "off"
            s.lease_until = time.monotonic() + 3
            s.fault = None
            return session.packet()
        except Exception as exc:
            s._fault(str(exc))
            raise

    def _motion(self, measured, previous=None):
        w = self.waypoints[self.index]
        sim = self.world.sim
        object_qpos = w.get("object_qpos", [])
        if (
            len(object_qpos) != len(sim.data.qpos) - 6
            or not np.isfinite(object_qpos).all()
        ):
            raise ValueError("Invalid rehearsed object state")
        sim.data.qpos[6:] = object_qpos
        sim.policy.held = w.get("held", False)
        sim.policy.contents = list(w.get("contents", []))
        goal = {k: w[k] for k in ("position", "quaternion", "opening_rad")}
        motion = CartesianMotion(
            self.service,
            self.world,
            measured,
            goal,
            guard=TaskGuard(sim, dict(goal, phase=w["phase"]), previous=previous),
        )
        motion.endpoint_required_frames = (
            6 if self.index == len(self.waypoints) - 1 else 1
        )
        motion.hold_on_arrival = self.index == len(self.waypoints) - 1
        return motion

    def advance(self, measured):
        if not self.active:
            return
        if self.session.closed or self.session.sim.running:
            raise ValueError("Scene changed during physical task")
        motion = self.service.manual
        self._report.observe(motion.error)
        if motion.phase != "holding":
            return
        self.index += 1
        if self.index < len(self.waypoints):
            # Arrival has a tolerance. Start the next scene estimate from the
            # measured endpoint and its last checked geometry, not an ideal
            # waypoint that may never have been reached exactly.
            previous = dict(
                motion.last_pose,
                object_qpos=motion.guard.data.qpos[6:].tolist(),
            )
            next_motion = self._motion(measured, previous=previous)
            # Preserve the bounded actuator ramp between intermediate endpoints.
            next_motion.tracker = motion.tracker
            next_motion.last = motion.last
            self.service.manual = next_motion
            self.message = f"Tool goal {self.index+1}/{len(self.waypoints)} · {self.waypoints[self.index]['phase']}"
            return
        self.phase = "completed"
        self.message = "Tool goals reached (encoder estimate). Physical grasp and placement are not verified."
        self.report = self._report.finish("completed", self.message)
        self._report = None
        session = self.session
        self.session = None
        self.service.stop(session.id)
        if self.service.fault == "Stopped; existing motor torque is preserved":
            self.service.fault = None
        else:
            self.phase = "paused"
            self.message = self.service.fault or "Final hold could not be confirmed"
            self.report.update(outcome="stopped", reason=self.message)
        session.broadcast(session.packet())

    def halt(self, message):
        if self.session is None:
            return
        session = self.session
        self.session = None
        if self._report:
            self.report = self._report.finish("stopped", message)
            self._report = None
        self.phase = "paused"
        self.message = message
        session.broadcast(session.packet())
