"""Bounded IK pick/place controller. Only actuator targets and weld state are written.

Grasp assist is deliberate: a soft constraint is enabled only near the selected
object after closure. Released objects move solely under MuJoCo physics.
"""

import math
import mujoco
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .catalog import profile


class PickPlacePolicy:
    def __init__(self, sim):
        self.sim = sim
        self.status = "idle"
        self.phase = "Ready"
        self.message = "Select an object to pick and a destination."
        self.success = False
        self.index = 0
        self.steps = []
        self.held = False
        self.elapsed = 0.0
        self.source = None
        self.target = None
        self.configuration = {}

    def packet(self):
        return dict(
            status=self.status,
            phase=self.phase,
            message=self.message,
            progress=1.0 if self.success else self.index / 9,
            success=self.success,
            graspAssist=True,
            held=self.held,
            source=self.source,
            target=self.target,
        )

    def ik(self, position, rotation, seed):
        m = self.sim.model
        d = mujoco.MjData(m)
        d.qpos[:] = self.sim.data.qpos
        sid = m.site("gripperframe").id
        bid = m.body("gripper").id
        lo, hi = m.jnt_range[:5].T

        def residual(q):
            d.qpos[:5] = q
            mujoco.mj_kinematics(m, d)
            r = d.xmat[bid].reshape(3, 3)
            return np.r_[
                d.site_xpos[sid] - position,
                0.07 * Rotation.from_matrix(rotation @ r.T).as_rotvec(),
            ]

        best = None
        for start in [
            seed[:5],
            [seed[0], -0.5, 1.0, 0.8, 0.05],
            [seed[0], 0.5, -0.5, 1.0, 0.05],
        ]:
            fit = least_squares(
                residual,
                np.clip(start, lo + 1e-6, hi - 1e-6),
                bounds=(lo, hi),
                max_nfev=160,
                ftol=1e-9,
                xtol=1e-9,
                gtol=1e-9,
            )
            if best is None or np.linalg.norm(fit.fun) < np.linalg.norm(best.fun):
                best = fit
            if (
                np.linalg.norm(fit.fun[:3]) < 0.002
                and np.linalg.norm(fit.fun[3:]) < 0.005
            ):
                break
        if np.linalg.norm(best.fun[:3]) > 0.008 or np.linalg.norm(best.fun[3:]) > 0.018:
            raise ValueError(
                f"Target outside comfortable reach (IK error {np.linalg.norm(best.fun[:3]) * 1000:.0f} mm). Move objects closer to the arm or load the example."
            )
        return np.r_[best.x, 0.65]

    def start(self):
        if self.status == "running":
            return
        s = self.sim
        task = s.scene.task
        if not task.source or not task.target:
            raise ValueError(
                "Select an object to pick and an object to place into/on first, or load the example."
            )
        self.source, self.target = task.source, task.target
        src = next(o for o in s.scene.objects if o.id == self.source)
        dst = next(o for o in s.scene.objects if o.id == self.target)
        if not src.collision or not dst.collision:
            raise ValueError("Enable collision on both task objects.")
        sp, dp = profile(src), profile(dst)
        if dp["family"] not in ("cup", "bowl", "plate", "cube", "mesh"):
            raise ValueError("Choose a cup, plate or solid support as the destination.")
        source = s.data.body(f"object_{src.id}")
        target = s.data.body(f"object_{dst.id}")
        if target.xmat.reshape(3, 3)[2, 2] < 0.95:
            raise ValueError("Place the destination upright before running.")
        grip = source.xpos.copy()
        if sp["family"] == "spoon":
            grip += source.xmat.reshape(3, 3) @ np.array(
                [sp["grasp"] * src.scale, 0, 0]
            )
        self.grip_point = grip
        # Arm pitch plane is radial; gripper's local Z points away from fingers.
        shoulder = s.data.body("shoulder").xpos
        yaw = math.atan2(
            grip[1] - shoulder[1], grip[0] - shoulder[0]
        ) + self.configuration.get("yaw_offset", 0)
        radial = np.array([math.cos(yaw), math.sin(yaw), 0.0])
        tangent = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
        down = np.column_stack([radial, tangent, [0, 0, 1]])
        seed = s.data.qpos[:6].copy()
        plans = []

        def move(label, pos, rot, opening=0.65, duration=1.8):
            nonlocal seed
            seed = self.ik(np.array(pos), rot, seed)
            seed[5] = opening
            plans.append((label, seed.copy(), duration))

        lift = self.configuration.get("lift", 0.10)
        move("Approach", grip + [0, 0, lift], down)
        move("Descend", grip + [0, 0, 0.003], down, duration=1.5)
        closed = seed.copy()
        closed[5] = -0.03
        plans.append(("Grasp", closed, 0.8))
        move("Lift", grip + [0, 0, lift], down, -0.03)
        # The remaining path is planned from the measured grasp transform,
        # after closing. Thin objects can rotate slightly while being grasped.
        self.steps = plans
        self.index = 0
        self.start_q = s.data.qpos[:6].copy()
        self.started = float(s.data.time)
        self.phase = plans[0][0]
        self.status = "running"
        self.success = False
        self.held = False
        self.message = "IK policy · proximity-gated grasp assist"
        self.initial_source_z = float(source.xpos[2])
        self.lifted = False

    def attach(self):
        s = self.sim
        m, d = s.model, s.data
        b1 = m.body("gripper").id
        b2 = s.object_bodies[self.source]
        obj = next(o for o in s.scene.objects if o.id == self.source)
        actual = d.xpos[b2].copy()
        if profile(obj)["family"] == "spoon":
            actual += d.xmat[b2].reshape(3, 3) @ np.array(
                [profile(obj)["grasp"] * obj.scale, 0, 0]
            )
        distance = np.linalg.norm(d.site("gripperframe").xpos - actual)
        if distance > 0.025 or d.qpos[5] > 0.25:
            self.fail(
                f"Grasp missed ({distance * 1000:.0f} mm). Reposition the object or reload the example."
            )
            return
        eq = m.equality(f"grasp_{self.source}").id
        r = d.xmat[b1].reshape(3, 3)
        m.eq_data[eq, 3:6] = r.T @ (d.xpos[b2] - d.xpos[b1])
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, (r.T @ d.xmat[b2].reshape(3, 3)).reshape(-1))
        m.eq_data[eq, 6:10] = q
        d.eq_active[eq] = True
        self.held = True

    def plan_delivery(self):
        s = self.sim
        m, d = s.model, s.data
        src = next(o for o in s.scene.objects if o.id == self.source)
        dst = next(o for o in s.scene.objects if o.id == self.target)
        sp, dp = profile(src), profile(dst)
        b = d.body("gripper")
        a = d.body(f"object_{self.source}")
        target = d.body(f"object_{self.target}")
        r = b.xmat.reshape(3, 3)
        bowl = a.xpos + a.xmat.reshape(3, 3) @ np.array(
            [sp.get("bowl", 0) * src.scale if sp["family"] == "spoon" else 0, 0, 0]
        )
        point = r.T @ (bowl - b.xpos)
        inserting = sp["family"] == "spoon" and dp["family"] == "cup"
        axis_index = 0 if sp["family"] == "spoon" else 2
        world_axis = a.xmat.reshape(3, 3)[:, axis_index]
        axis = r.T @ world_axis
        desired_axis = (
            np.array([0, 0, -1])
            if inserting
            else (
                np.array([world_axis[0], world_axis[1], 0])
                if sp["family"] == "spoon"
                else np.array([0, 0, 1])
            )
        )
        desired_axis = desired_axis / np.linalg.norm(desired_axis)
        seed = self.steps[-1][1].copy()
        scratch = mujoco.MjData(m)
        scratch.qpos[:] = d.qpos
        lo, hi = m.jnt_range[:5].T

        def carry(label, position, duration):
            nonlocal seed

            def residual(q):
                scratch.qpos[:5] = q
                mujoco.mj_kinematics(m, scratch)
                hand = scratch.body("gripper")
                rotation = hand.xmat.reshape(3, 3)
                orientation = rotation @ axis
                # For shallow receivers keep the spoon level but let its yaw
                # follow the arm's reachable plane instead of overconstraining it.
                angle_error = (
                    np.array([orientation[2]])
                    if sp["family"] == "spoon" and not inserting
                    else orientation - desired_axis
                )
                return np.r_[
                    hand.xpos + rotation @ point - position, 0.06 * angle_error
                ]

            best = None
            for start in [
                seed[:5],
                [seed[0], -0.8, 0.8, 0, 0.05],
                [seed[0], -0.4, 0.8, -0.4, 1.0],
            ]:
                fit = least_squares(
                    residual,
                    np.clip(start, lo + 1e-6, hi - 1e-6),
                    bounds=(lo, hi),
                    max_nfev=200,
                )
                if best is None or np.linalg.norm(fit.fun) < np.linalg.norm(best.fun):
                    best = fit
            if (
                np.linalg.norm(best.fun[:3]) > 0.008
                or np.linalg.norm(best.fun[3:]) > 0.018
            ):
                raise ValueError(
                    "Cannot orient the grasped object over this destination. Move it closer or reload the example."
                )
            seed = np.r_[best.x, -0.03]
            self.steps.append((label, seed.copy(), duration))

        height = dp["dimensions"][2] * dst.scale
        clearance = self.configuration.get("transfer_clearance", 0.13)
        if inserting:
            carry(
                "Transfer", target.xpos + [0, 0, max(clearance, height / 2 + 0.06)], 2.8
            )
            carry(
                "Place",
                target.xpos + [0, 0, min(0.012 * dst.scale, height * 0.15)],
                2.0,
            )
        else:
            # Place the measured carried point over the receiving surface.
            z = (
                -height / 2 + dp.get("thickness", 0.004) * dst.scale
                if dp["family"] in ("bowl", "plate")
                else height / 2
            )
            position = target.xpos + [
                0,
                0,
                z + sp["dimensions"][2] * src.scale / 2 + 0.014,
            ]
            carry("Transfer", position + [0, 0, clearance], 2.8)
            carry("Place", position, 2.0)
        opened = seed.copy()
        opened[5] = 0.8
        self.steps.append(("Release", opened, 0.8))
        scratch.qpos[:6] = seed
        mujoco.mj_forward(m, scratch)
        retreat = self.ik(
            scratch.site("gripperframe").xpos + [0, 0, 0.08],
            scratch.body("gripper").xmat.reshape(3, 3).copy(),
            seed,
        )
        retreat[5] = 0.8
        self.steps.extend([("Retreat", retreat, 1.7), ("Verify", retreat, 2.5)])

    def release(self):
        self.sim.data.eq_active[:] = False
        self.held = False

    def cancel(self):
        self.release()
        self.status = "cancelled"
        self.phase = "Stopped"
        self.message = "Task stopped. Objects released."
        self.sim.data.ctrl[:] = self.sim.data.qpos[:6]

    def fail(self, message):
        self.release()
        self.status = "failed"
        self.phase = "Needs attention"
        self.message = message
        self.sim.running = False

    def verify(self):
        s = self.sim
        d = s.data
        src = next(o for o in s.scene.objects if o.id == self.source)
        dst = next(o for o in s.scene.objects if o.id == self.target)
        a = d.body(f"object_{src.id}")
        b = d.body(f"object_{dst.id}")
        sp, dp = profile(src), profile(dst)
        relative = b.xmat.reshape(3, 3).T @ (a.xpos - b.xpos)
        if sp["family"] == "spoon":
            bowl = a.xpos + a.xmat.reshape(3, 3) @ np.array(
                [sp["bowl"] * src.scale, 0, 0]
            )
            rel = b.xmat.reshape(3, 3).T @ (bowl - b.xpos)
            inside = (
                np.linalg.norm(rel[:2])
                < (dp.get("rim", dp["dimensions"][0] / 2) - 0.005) * dst.scale
                and -dp["dimensions"][2] / 2 * dst.scale - 0.003
                < rel[2]
                < dp["dimensions"][2] / 2 * dst.scale + 0.006
            )
        else:
            radius = (dp.get("rim", min(dp["dimensions"][:2]) / 2) - 0.003) * dst.scale
            inside = (
                np.linalg.norm(relative[:2]) < radius
                and relative[2] > -dp["dimensions"][2] * dst.scale / 2
                and relative[2]
                < dp["dimensions"][2] * dst.scale / 2
                + sp["dimensions"][2] * src.scale
                + 0.015
            )
        adr = mujoco.mj_name2id(
            s.model, mujoco.mjtObj.mjOBJ_BODY, f"object_{self.source}"
        )
        dof = s.model.jnt_dofadr[s.model.body_jntadr[adr]]
        stable = np.linalg.norm(d.qvel[dof : dof + 3]) < 0.03
        upright = b.xmat.reshape(3, 3)[2, 2] > 0.9
        self.success = bool(
            inside and stable and upright and self.lifted and not self.held
        )
        self.status = "succeeded" if self.success else "failed"
        self.phase = "Complete" if self.success else "Needs attention"
        self.message = (
            "Object released and settled in the destination."
            if self.success
            else "Object did not settle in the destination. Reload the example or adjust the task."
        )
        s.running = False

    def update(self):
        if self.status != "running":
            return
        s = self.sim
        self.lifted |= (
            s.data.xpos[s.object_bodies[self.source], 2] > self.initial_source_z + 0.06
        )
        label, q, duration = self.steps[self.index]
        elapsed = float(s.data.time) - self.started
        t = min(1.0, elapsed / duration)
        blend = t * t * (3 - 2 * t)
        s.data.ctrl[:] = self.start_q + (q - self.start_q) * blend
        if elapsed < duration:
            return
        if label == "Grasp":
            self.attach()
            if self.status == "failed":
                return
            try:
                self.plan_delivery()
            except ValueError as exc:
                self.fail(str(exc))
                return
        if label == "Release":
            self.release()
        if label == "Verify":
            self.verify()
            return
        self.index += 1
        self.start_q = s.data.ctrl.copy()
        self.started = float(s.data.time)
        self.phase = self.steps[self.index][0]
        # Release at beginning of opening so no invisible hold during retreat.
        if self.phase == "Release":
            self.release()
