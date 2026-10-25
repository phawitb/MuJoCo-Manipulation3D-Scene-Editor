"""Contact-only IK pick/place controller. Writes actuator targets only."""

import mujoco
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .catalog import profile
from .grasp import jaw_contacts, cup_approach_clearance, CUP_MIN_CLEARANCE
from .contents import find_contents, contents_issue
from .safety import collision_issue, swept_collision


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
        self.contents = []
        self.minimum_approach_clearance = CUP_MIN_CLEARANCE
        self.contact = jaw_contacts(sim, None)
        self.contact_since = None
        self.lost_since = None
        self.failure_settle_until = None

    def packet(self):
        return dict(
            status=self.status,
            phase=self.phase,
            message=self.message,
            progress=1.0 if self.success else self.index / 9,
            success=self.success,
            graspAssist=False,
            # Report the completed physics state, including passive motion after
            # cancellation/failure; controller contact is sampled before a step.
            grip=jaw_contacts(self.sim, self.source),
            held=self.held,
            source=self.source,
            target=self.target,
            contents=list(self.contents),
        )

    def ik(self, position, rotation, seed, pinch=None, opening=0.65):
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
            if pinch is not None:
                return np.r_[
                    d.xpos[bid] + r @ pinch - position,
                    0.07 * (r[:, 0] - rotation[:, 0]),
                    0.002 * (r[:, 2] - rotation[:, 2]),
                ]
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
            d.qpos[:6] = np.r_[fit.x, opening]
            mujoco.mj_forward(m, d)
            if collision_issue(
                self.sim, d, kinematic=True, ignore_source=True
            ) or swept_collision(self.sim, seed, np.r_[fit.x, opening], d):
                continue
            if best is None or np.linalg.norm(fit.fun) < np.linalg.norm(best.fun):
                best = fit
            if (
                np.linalg.norm(fit.fun[:3]) < 0.002
                and np.linalg.norm(fit.fun[3:]) < 0.005
            ):
                break
        if best is None:
            raise ValueError(
                "No collision-free grasp pose within reach. Reposition the task."
            )
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
        dp = profile(dst)
        if dp["family"] not in ("cup", "bowl", "plate", "cube", "mesh"):
            raise ValueError("Choose a cup, plate or solid support as the destination.")
        source = s.data.body(f"object_{src.id}")
        target = s.data.body(f"object_{dst.id}")
        if target.xmat.reshape(3, 3)[2, 2] < 0.95:
            raise ValueError("Place the destination upright before running.")
        self.contents = find_contents(s, self.source)
        self.initial_source_z = float(source.xpos[2])
        self.lifted = False
        self.steps = [("Settle", s.data.qpos[:6].copy(), 0.5)]
        self.index = 0
        self.start_q = s.data.qpos[:6].copy()
        self.started = float(s.data.time)
        self.phase = "Settle"
        self.status = "running"
        self.success = self.held = False
        self.message = "Contact-only IK · gravity and friction"
        self.contact_since = self.lost_since = None

    def plan_pick(self):
        s = self.sim
        src = next(o for o in s.scene.objects if o.id == self.source)
        sp = profile(src)
        source = s.data.body(f"object_{src.id}")
        grip = source.xpos.copy()
        if sp["family"] == "spoon":
            grip += source.xmat.reshape(3, 3) @ np.array(
                [
                    (sp["grasp"] + self.configuration.get("grasp_along_offset", 0))
                    * src.scale,
                    0,
                    0,
                ]
            )
        rim_grasp = sp["family"] == "cup"
        if rim_grasp:
            if source.xmat.reshape(3, 3)[2, 2] < 0.98:
                raise ValueError("Stand the cup upright before grasping its rim.")
            toward_base = s.data.body("base").xpos - source.xpos
            angle = np.arctan2(toward_base[1], toward_base[0]) + self.configuration.get(
                "rim_angle", 0
            )
            rim_direction = np.array([np.cos(angle), np.sin(angle), 0.0])
            depth = 0.006 * src.scale
            radius = (sp["rim"] - sp["thickness"] / 2) * src.scale
            radius -= (
                depth * (sp["rim"] - sp.get("base", sp["rim"])) / sp["dimensions"][2]
            )
            # Inset the pinch centre so the inner finger clears the tapered wall.
            radius -= 0.002 * src.scale
            grip = (
                source.xpos
                + radius * rim_direction
                + np.array([0, 0, sp["dimensions"][2] * src.scale / 2 - depth])
            )
        self.grip_point = grip
        # Close across the handle, not along an arbitrary radial direction.
        long_axis = source.xmat.reshape(3, 3)[:, 0]
        # An exposed upright handle needs a pinch-axis constraint, not a full
        # six-dimensional pose that this five-axis arm cannot generally reach.
        upright = sp["family"] == "spoon" and abs(long_axis[2]) > 0.7
        across = (
            source.xmat.reshape(3, 3)[:, 1].copy()
            if upright
            else np.array([-long_axis[1], long_axis[0], 0.0])
        )

        if rim_grasp:
            across = rim_direction
        if np.linalg.norm(across) < 0.2:
            raise ValueError(
                "This grasp requires the utensil lying flat. Reposition it before calculating."
            )
        if upright:
            across[2] = 0
        across /= np.linalg.norm(across)
        if self.configuration.get("reverse_grasp", False):
            across *= -1
        up = np.array([0, 0, 1])
        down = np.column_stack([across, np.cross(up, across), up])
        width = (
            sp["thickness"]
            if rim_grasp
            else (
                0.014
                if src.asset == "kalas_spoon"
                else 0.006 if src.asset == "spoon" else sp["dimensions"][1]
            )
        ) * src.scale
        if width > 0.065:
            raise ValueError(
                "Object is too wide for this gripper at the selected grasp."
            )
        pinch = np.array(
            [
                -0.008 + width / 2,
                0,
                (
                    -0.1025
                    if src.asset == "spoon"
                    else -0.104 if sp["family"] == "spoon" else -0.098
                ),
            ]
        )
        pinch[2] += self.configuration.get("grasp_depth_offset", 0)
        offset = s.model.site_pos[s.model.site("gripperframe").id] - pinch
        # Centre a generous approach gap around a cup rim. This is an asymmetric
        # gripper: opening the moving jaw alone leaves the fixed finger tight
        # against the wall. Re-centre the open pose, then return to the pinch
        # pose as the fingers close, coordinating arm motion with the moving jaw.
        clearance = 0.020 if rim_grasp else 0.005
        opening = float(np.clip((width + clearance - 0.016) / 0.078, -0.08, 0.7))
        approach_pinch = pinch.copy()
        if rim_grasp:
            approach_pinch[0] += clearance / 2
        seed = s.data.qpos[:6].copy()
        plans = []

        def move(label, pos, rot, opening=opening, duration=1.8):
            nonlocal seed
            seed = (
                self.ik(
                    np.array(pos),
                    rot,
                    seed,
                    pinch=approach_pinch if rim_grasp and opening > 0 else pinch,
                    opening=opening,
                )
                if upright or rim_grasp
                else self.ik(np.array(pos) + rot @ offset, rot, seed, opening=opening)
            )
            seed[5] = opening
            plans.append((label, seed.copy(), duration))

        lift = self.configuration.get("lift", 0.075 if rim_grasp else 0.10)
        move(
            "Approach",
            grip + [0, 0, min(lift, 0.035) if upright or rim_grasp else lift],
            down,
        )
        move("Descend", grip, down, duration=1.5)
        closed = (
            self.ik(grip, down, seed, pinch=pinch, opening=-0.17)
            if rim_grasp
            else seed.copy()
        )
        closed[5] = -0.17
        plans.append(("Grasp", closed, 2.5))
        if rim_grasp:
            seed = closed.copy()
        move("Lift", grip + [0, 0, lift], down, -0.17)
        # The remaining path is planned from the measured grasp transform,
        # after closing. Thin objects can rotate slightly while being grasped.
        self.steps.extend(plans)

    def confirm_grasp(self):
        self.contact = jaw_contacts(self.sim, self.source)
        if (
            not self.contact["secure"]
            or self.contact_since is None
            or self.sim.data.time - self.contact_since < 0.08
        ):
            self.fail(
                "Grasp missed: both jaws must maintain opposing contact. Reposition the object."
            )
            return
        self.held = True
        self.lost_since = None

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
        # Center the utensil on a plate. Aiming its bowl at the plate center
        # pulls the hand back toward the robot base and can fold it into itself.
        placement_point = a.xpos if dp["family"] == "plate" else bowl
        point = r.T @ (placement_point - b.xpos)
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
        desired_axis = desired_axis / max(np.linalg.norm(desired_axis), 1e-12)
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
                scratch.qpos[:6] = np.r_[fit.x, 0.8 if label == "Retreat" else -0.17]
                mujoco.mj_forward(m, scratch)
                if collision_issue(
                    s, scratch, kinematic=True, ignore_source=True
                ) or swept_collision(
                    s, seed, np.r_[fit.x, 0.8 if label == "Retreat" else -0.17], scratch
                ):
                    continue
                if best is None or np.linalg.norm(fit.fun) < np.linalg.norm(best.fun):
                    best = fit
            if best is None:
                raise ValueError(
                    f"No collision-free {label.lower()} pose within reach. Reposition the destination."
                )
            if (
                np.linalg.norm(best.fun[:3]) > 0.008
                or np.linalg.norm(best.fun[3:]) > 0.018
            ):
                raise ValueError(
                    "Cannot orient the grasped object over this destination. Move it closer or reload the example."
                )
            seed = np.r_[best.x, -0.17]
            self.steps.append((label, seed.copy(), duration))

        height = dp["dimensions"][2] * dst.scale
        clearance = self.configuration.get(
            "transfer_clearance", 0.035 if sp["family"] == "cup" else 0.13
        )
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
            # Release above the rim; driving the hand down to the bowl floor
            # pushes the utensil against the vessel and cannot be a valid place.
            position = target.xpos + [
                0,
                0,
                height / 2 + sp["dimensions"][2] * src.scale / 2 + 0.008,
            ]
            carry("Transfer", position + [0, 0, clearance], 2.8)
            carry("Place", position, 2.0)
        opened = seed.copy()
        opened[5] = 0.8
        self.steps.append(("Release", opened, 0.8))
        # Use the same reachable carried-point constraint for withdrawal.
        place_point = (
            target.xpos + [0, 0, min(0.012 * dst.scale, height * 0.15)]
            if inserting
            else position
        )
        carry(
            "Retreat",
            place_point + [0, 0, 0.035 if sp["family"] == "cup" else 0.08],
            1.7,
        )
        label, retreat, duration = self.steps[-1]
        retreat[5] = 0.8
        self.steps[-1] = (label, retreat, duration)
        self.steps.append(("Verify", retreat.copy(), 2.5))

    def release(self):
        self.held = False

    def cancel(self):
        self.release()
        self.status = "cancelled"
        self.phase = "Stopped"
        self.message = "Task stopped. Objects released."
        self.sim.data.ctrl[:] = self.sim.data.qpos[:6]
        self.sim.data.ctrl[5] = 0.8

    def fail(self, message):
        self.release()
        self.success = False
        self.status = "failed"
        self.phase = "Needs attention"
        self.message = message
        self.sim.data.ctrl[:] = self.sim.data.qpos[:6]
        self.sim.data.ctrl[5] = 0.8
        self.failure_settle_until = float(self.sim.data.time) + 1.5
        self.sim.running = True

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
        stable = (
            np.linalg.norm(d.qvel[dof : dof + 3]) < 0.03
            and np.linalg.norm(d.qvel[dof + 3 : dof + 6]) < 0.3
        )
        supported = False
        for index, contact in enumerate(d.contact):
            bodies = {int(s.model.geom_bodyid[g]) for g in contact.geom}
            if bodies == {s.object_bodies[self.source], s.object_bodies[self.target]}:
                force = np.zeros(6)
                mujoco.mj_contactForce(s.model, d, index, force)
                supported |= force[0] > 0.005
        grip = jaw_contacts(s, self.source)
        released = grip["leftForce"] + grip["rightForce"] < 0.02
        upright = b.xmat.reshape(3, 3)[2, 2] > 0.9
        if sp["family"] == "cup":
            upright = upright and a.xmat.reshape(3, 3)[2, 2] > 0.95
            if dp["family"] == "plate":
                inside = (
                    inside
                    and np.linalg.norm(relative[:2])
                    + sp.get("base", sp["rim"]) * src.scale
                    < dp["rim"] * dst.scale
                )
        content_error = (
            contents_issue(s, self.source, self.contents, settled=True)
            if self.contents
            else None
        )
        self.success = bool(
            not content_error
            and inside
            and stable
            and upright
            and supported
            and released
            and self.lifted
            and not self.held
        )
        self.status = "succeeded" if self.success else "failed"
        self.phase = "Complete" if self.success else "Needs attention"
        self.message = (
            "Object released and settled in the destination."
            if self.success
            else content_error
            or "Object did not settle in the destination. Reload the example or adjust the task."
        )
        s.running = False

    def update(self):
        if self.status == "failed" and self.failure_settle_until is not None:
            if self.sim.data.time >= self.failure_settle_until:
                self.sim.running = False
            return
        if self.status != "running":
            return
        s = self.sim
        if self.lifted and self.contents:
            issue = contents_issue(s, self.source, self.contents)
            if issue:
                self.fail(issue)
                return
        self.contact = jaw_contacts(s, self.source)
        if self.contact["secure"]:
            if self.contact_since is None:
                self.contact_since = float(s.data.time)
            self.lost_since = None
        else:
            self.contact_since = None
            if self.held and self.lost_since is None:
                self.lost_since = float(s.data.time)
        if (
            self.held
            and self.lost_since is not None
            and s.data.time - self.lost_since > 0.10
        ):
            self.fail(
                "Object slipped from the gripper. Physics continues while it falls; adjust the grasp."
            )
            return
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
        # Closing fingers intentionally stop against the object, but the five
        # arm joints must actually reach each waypoint before advancing.
        if np.max(np.abs(s.data.qpos[:5] - q[:5])) > 0.03:
            self.fail(
                "Arm did not reach the commanded pose. Motion stopped; check obstacles and joint limits."
            )
            return
        # Contact can prevent closing, but retreat must wait for an opening
        # jaw. Starting the retreat early can sweep a finger into the object.
        if label == "Release" and abs(s.data.qpos[5] - q[5]) > 0.03:
            if elapsed >= duration + 1.5:
                self.fail(
                    "Gripper did not open before retreat. Check the grasp and obstructions."
                )
            return
        if label == "Descend":
            source = next(o for o in s.scene.objects if o.id == self.source)
            if profile(source)["family"] == "cup":
                clearance = cup_approach_clearance(s, self.source)
                if clearance < self.minimum_approach_clearance:
                    self.fail(
                        f"Cup approach clearance is only {clearance * 1000:.1f} mm; "
                        f"at least {self.minimum_approach_clearance * 1000:g} mm is required on both sides before closing. "
                        "Try another rim direction or reposition the cup."
                    )
                    return
        if label == "Settle":
            try:
                self.plan_pick()
            except ValueError as exc:
                self.fail(str(exc))
                return
        if label == "Grasp":
            self.confirm_grasp()
            if self.status == "failed":
                return
        if label == "Lift":
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
