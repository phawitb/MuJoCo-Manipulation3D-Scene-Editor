"""Session-locked simulation guard and measured-pose mirroring."""

import math


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
            return s.sim.data.qpos[:6].tolist()

    def validate(self, start, end):
        import mujoco
        import numpy as np
        from ...safety import collision_issue

        s = self.session()
        with s.lock:
            m = s.sim.model
            if any(
                not math.isfinite(v) or v < lo or v > hi
                for v, (lo, hi) in zip(end, m.jnt_range[:6])
            ):
                raise ValueError("Simulation joint limit exceeded")
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
