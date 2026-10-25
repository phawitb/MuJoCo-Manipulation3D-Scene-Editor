"""Session-locked simulation guard and measured-pose mirroring."""

import math


def hardware_target(values, limits):
    from ...safety import JOINT_TOLERANCE

    # MuJoCo joint stops are compliant. Project only the already permitted
    # numerical residual; physical goals and measured-pose guards stay strict.
    if any(
        not math.isfinite(q) or not lo - JOINT_TOLERANCE <= q <= hi + JOINT_TOLERANCE
        for q, (lo, hi) in zip(values, limits)
    ):
        raise ValueError("Simulation joint limit exceeded")
    return [max(lo, min(hi, q)) for q, (lo, hi) in zip(values, limits)]


class GymBridge:
    def __init__(self, registry, session_id):
        self.registry = registry
        self.session_id = session_id
        self.check_alive()

    def session(self):
        session = self.registry.get(self.session_id)
        if session.closed:
            raise ValueError("Gym session closed")
        return session

    def check_alive(self):
        self.session()

    def get(self):
        s = self.session()
        with s.lock:
            return hardware_target(s.sim.data.qpos[:6], s.sim.model.jnt_range[:6])

    def limits(self):
        s = self.session()
        with s.lock:
            return s.sim.model.jnt_range[:6].tolist()

    def validate(self, start, end):
        import mujoco
        import numpy as np
        from ...safety import collision_issue

        s = self.session()
        with s.lock:
            m = s.sim.model
            for i, (v, (lo, hi)) in enumerate(zip(end, m.jnt_range[:6])):
                if not math.isfinite(v) or not lo <= v <= hi:
                    raise ValueError(
                        f"Simulation joint limit exceeded: joint {i + 1}, "
                        f"requested {v:.5f}, allowed {lo:.5f} to {hi:.5f} rad"
                    )
            scratch = mujoco.MjData(m)
            scratch.qpos[:] = s.sim.data.qpos
            count = max(
                1, math.ceil(max(abs(a - b) for a, b in zip(start, end)) / 0.02)
            )
            for f in np.linspace(0, 1, count + 1):
                scratch.qpos[:6] = np.asarray(start) + (np.asarray(end) - start) * f
                mujoco.mj_fwdPosition(m, scratch)
                issue = collision_issue(s.sim, scratch, kinematic=True)
                if issue:
                    raise ValueError("Simulation collision: " + issue)

    def set(self, q):
        import mujoco

        s = self.session()
        with s.lock:
            if s.sim.running or s.sim.policy.status == "running":
                s.sim.stop_policy()
            s.sim.running = False
            s.invalidate_plan()
            s.sim.data.qpos[:6] = q
            s.sim.data.qvel[:6] = 0
            s.sim.data.ctrl[:6] = q
            mujoco.mj_forward(s.sim.model, s.sim.data)
            s.sequence += 1
            s.plan_dirty = True
