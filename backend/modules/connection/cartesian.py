"""Encoder-estimated tool control; joint equality with Gym is not an objective."""

import math
import time
import mujoco
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .manual import ManualMotion, MotionGuard

POSITION_TOLERANCE_MM = 3.0
ORIENTATION_TOLERANCE_DEG = 3.0
OPENING_TOLERANCE_DEG = 1.5


def pose_error(measured, goal):
    a = Rotation.from_quat(measured["quaternion"])
    b = Rotation.from_quat(goal["quaternion"])
    return dict(
        position_mm=float(
            np.linalg.norm(np.asarray(measured["position"]) - goal["position"]) * 1000
        ),
        orientation_deg=float(np.degrees((b * a.inv()).magnitude())),
        opening_deg=math.degrees(abs(measured["opening_rad"] - goal["opening_rad"])),
    )


def arrived(error):
    return (
        error["position_mm"] <= POSITION_TOLERANCE_MM
        and error["orientation_deg"] <= ORIENTATION_TOLERANCE_DEG
        and error["opening_deg"] <= OPENING_TOLERANCE_DEG
    )


class ToolKinematics:
    def __init__(self, sim):
        self.model = sim.model
        self.data = mujoco.MjData(self.model)
        self.data.qpos[:] = sim.data.qpos
        self.site = self.model.site("gripperframe").id

    def pose(self, q):
        if len(q) != 6 or not np.isfinite(q).all():
            raise ValueError("Six finite measured angles required")
        self.data.qpos[:6] = q
        mujoco.mj_kinematics(self.model, self.data)
        return dict(
            position=self.data.site_xpos[self.site].tolist(),
            quaternion=Rotation.from_matrix(
                self.data.site_xmat[self.site].reshape(3, 3)
            )
            .as_quat()
            .tolist(),
            opening_rad=float(q[5]),
        )

    def solve(self, goal, measured, limits, guard, resolution=None, quantize=None):
        lo, hi = np.asarray(limits).T
        if not lo[5] <= goal["opening_rad"] <= hi[5]:
            raise ValueError("Gripper target exceeds calibrated joint range")
        reserve = 0.51 * np.asarray(resolution if resolution is not None else [0.0] * 6)
        lo, hi = lo + reserve, hi - reserve
        if np.any(lo >= hi):
            raise ValueError("Joint range is narrower than encoder resolution")
        opening = float(np.clip(goal["opening_rad"], lo[5], hi[5]))
        rotation = Rotation.from_quat(goal["quaternion"])

        position = np.asarray(goal["position"], dtype=float)

        def residual(q):
            pose = self.pose([*q, opening])
            return np.r_[
                np.asarray(pose["position"]) - position,
                0.07
                * (rotation * Rotation.from_quat(pose["quaternion"]).inv()).as_rotvec(),
            ]

        seeds = [
            measured[:5],
            [measured[0], -0.5, 1.0, 0.8, measured[4]],
            [measured[0], 0.5, -0.5, 1.0, measured[4]],
        ]
        failure = (
            "Tool target is unreachable with the requested orientation and joint limits"
        )
        for clearance in (0.0, 0.0005, 0.001):
            position = np.asarray(goal["position"]) + [0.0, 0.0, clearance]
            for seed in seeds:
                fit = least_squares(
                    residual,
                    np.clip(seed, lo[:5] + 1e-7, hi[:5] - 1e-7),
                    bounds=(lo[:5], hi[:5]),
                    max_nfev=100,
                    ftol=1e-9,
                    xtol=1e-9,
                    gtol=1e-9,
                )
                target = [*fit.x, opening]
                target = quantize(target) if quantize else target
                error = pose_error(self.pose(target), goal)
                # Reserve part of the arrival tolerance for feedback/quantization.
                if error["position_mm"] > 1 or error["orientation_deg"] > 1:
                    continue
                try:
                    guard.path(measured, target)
                except ValueError as exc:
                    failure = "Whole-arm path rejected: " + str(exc)
                    continue
                return target
        raise ValueError(failure)


class CartesianMotion(ManualMotion):
    def __init__(self, service, session, measured, goal, guard=None):
        self.kinematics = ToolKinematics(session.sim)
        self.goal = dict(goal)
        self.goal["quaternion"] = (
            self.goal.get("quaternion") or self.kinematics.pose(measured)["quaternion"]
        )
        self.goal["opening_rad"] = (
            measured[5]
            if self.goal.get("opening_rad") is None
            else self.goal["opening_rad"]
        )
        guard = guard or MotionGuard(session.sim, measured)
        target = self.kinematics.solve(
            self.goal,
            measured,
            service._control_limits(),
            guard,
            resolution=[c.radians_per_tick for c in service.calibration.joints],
            quantize=lambda q: [
                service._angle(i, raw) for i, raw in enumerate(service._raw(q))
            ],
        )
        super().__init__(service, session, measured, target, guard=guard)
        self.endpoint_frames = 0
        self.endpoint_required_frames = 6
        self.hold_on_arrival = True
        self.error = pose_error(self.kinematics.pose(measured), self.goal)
        self.last_pose = self.kinematics.pose(measured)

    def tick(self, measured):
        if (
            self.session.closed
            or self.session.sim.model is not self.guard.model
            or self.session.sim.running
        ):
            raise ValueError("Scene changed during tool control")
        self.guard.observe(measured)
        self.last_pose = self.kinematics.pose(measured)
        self.error = pose_error(self.last_pose, self.goal)
        self.endpoint_frames = self.endpoint_frames + 1 if arrived(self.error) else 0
        if self.endpoint_frames:
            # Do not keep driving toward an arbitrary IK joint solution once
            # the tool is within tolerance. Hold first, then confirm arrival.
            if self.endpoint_frames == 1 and self.hold_on_arrival:
                self.service._hold(measured_only=True)
                self.tracker.reset(measured)
            self.last = time.monotonic()
            self.phase = (
                "holding"
                if self.endpoint_frames >= self.endpoint_required_frames
                else "moving"
            )
            return
        super().tick(measured)
        self.phase = "moving"

    def status(self):
        return dict(
            phase=self.phase,
            frame="world",
            tool_frame="gripperframe",
            measurement_source="encoder_fk",
            object_verified=False,
            measured=self.last_pose,
            target=self.goal,
            error=self.error,
            tolerances=dict(
                position_mm=POSITION_TOLERANCE_MM,
                orientation_deg=ORIENTATION_TOLERANCE_DEG,
                opening_deg=OPENING_TOLERANCE_DEG,
            ),
        )


def move_tool(service, request):
    s = service
    with s.lock:
        s._owner(request.session_id)
        s._calibrated()
        if request.control_epoch != s.control_epoch:
            raise ValueError("Tool command expired after Stop or a connection change")
        if s._preparing or s.execution.active or s.sync_mode != "off" or s.recovering:
            raise ValueError("Stop the current task before tool control")
        session = s.bridge.session()
        try:
            with session.lock:
                if session.sim.running:
                    raise ValueError("Pause simulation before tool control")
                measured = s._read()
                s._raw(measured)
                if not all(row["torque"] for row in s.telemetry):
                    raise ValueError("Turn Torque On before moving the robot")
                motion = CartesianMotion(
                    s,
                    session,
                    measured,
                    request.model_dump(exclude={"session_id", "control_epoch"}),
                )
                s._raw(motion.target)
                if time.monotonic() - s.measured_at > 0.2:
                    raise ValueError("Stale feedback after tool path validation; retry")
                # Own the transition before writes, so a partial bus failure holds.
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
                s.lease_until = time.monotonic() + 3
                s.fault = None
                return s.status()
        except Exception as exc:
            if s.enabled or s.manual is not None or isinstance(exc, OSError):
                s._fault(str(exc))
            raise
