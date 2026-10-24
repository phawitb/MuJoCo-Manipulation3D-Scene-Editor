"""Whole-arm contact rules shared by rehearsal, IK and execution.

MuJoCo contacts are compliant. Tiny finger/table contact during a tabletop grasp
is allowed; sustained body collisions are never a valid way to reach a target.
"""

import numpy as np

SELF_TOLERANCE = 0.00002  # 20 micrometres, numerical contact tolerance
BODY_TOLERANCE = 0.0001
GRASP_TOLERANCE = 0.0015


def collision_issue(sim, data=None, *, kinematic=False, ignore_source=False):
    m = sim.model
    d = sim.data if data is None else data
    objects = sim.object_bodies
    source = objects.get(sim.scene.task.source)
    robot = set(range(1, m.nbody)) - set(objects.values())
    jaws = {m.body("gripper").id, m.body("moving_jaw_so101_v1").id}
    names = {objects[o.id]: o.name for o in sim.scene.objects}
    hand = d.body("gripper")
    held = getattr(sim.policy, "held", False)
    # Loose cargo moves through contact with the cup but still occupies space.
    carried = {source} | {
        objects[oid] for oid in getattr(sim.policy, "contents", []) if oid in objects
    }
    for c in d.contact:
        a, b = (int(m.geom_bodyid[g]) for g in c.geom)
        if ignore_source and source in (a, b):
            continue
        if a in robot and b in robot:
            tolerance = 0 if kinematic else SELF_TOLERANCE
            kind = "Arm self-collision"
        elif a in robot or b in robot:
            arm, other = (a, b) if a in robot else (b, a)
            tip = (
                arm in jaws
                and (hand.xmat.reshape(3, 3).T @ (c.pos - hand.xpos))[2] < -0.075
            )
            if other == source and tip:
                tolerance = GRASP_TOLERANCE
                kind = "Grasp penetration"
            else:
                tolerance = (
                    0 if kinematic and not (tip and other == 0) else BODY_TOLERANCE
                )
                kind = "Arm collision"
        elif held and (a in carried or b in carried):
            # Include protruding cargo against external obstacles, as well as
            # cup/cargo contacts. Ordinary touching is allowed; deep penetration
            # is not, even when an item remains geometrically inside the cup.
            tolerance = 0.0015
            kind = "Held object collision"
        else:
            continue
        if c.dist >= -tolerance:
            continue

        def name(body, geom):
            label = names.get(body) or (
                m.body(body).name if body else m.geom(geom).name
            )
            return (
                "wrist camera" if label == "camera_mount" else label.replace("_", " ")
            )

        pair = [name(body, geom) for body, geom in zip((a, b), c.geom)]
        return f"{kind}: {' / '.join(pair)} ({-c.dist * 1000:.2f} mm)."
    return None


def joint_issue(sim):
    q = sim.data.qpos[:6]
    limits = sim.model.jnt_range[:6]
    if not np.isfinite(q).all():
        return "Robot joint state is not finite."
    outside = np.flatnonzero((q < limits[:, 0] - 0.002) | (q > limits[:, 1] + 0.002))
    if len(outside):
        return f"Joint limit reached: {sim.model.joint(int(outside[0])).name}."
    return None


def swept_collision(sim, start, end, data=None):
    """Sample the commanded joint interpolation, not just the tool endpoints.

    This is an IK prefilter; the complete rehearsal still checks actual contacts
    every physics step, including the carried object and actuator dynamics.
    """
    import mujoco

    scratch = data if data is not None else mujoco.MjData(sim.model)
    scratch.qpos[:] = sim.data.qpos
    count = max(1, int(np.ceil(np.max(np.abs(np.asarray(end) - start)) / 0.04)))
    for fraction in np.linspace(0, 1, count + 1):
        scratch.qpos[:6] = np.asarray(start) + (np.asarray(end) - start) * fraction
        mujoco.mj_fwdPosition(sim.model, scratch)
        issue = collision_issue(sim, scratch, kinematic=True, ignore_source=True)
        if issue:
            return issue
    return None
