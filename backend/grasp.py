"""Measured contact support. No forces or constraints are created here."""

import mujoco
import numpy as np


def jaw_contacts(sim, source):
    result = dict(
        leftForce=0.0, rightForce=0.0, opposing=False, secure=False, maxPenetration=0.0
    )
    if source not in sim.object_bodies:
        return result
    m, d = sim.model, sim.data
    source_id = sim.object_bodies[source]
    jaw_ids = [m.body("gripper").id, m.body("moving_jaw_so101_v1").id]
    forces = np.zeros(2)
    normals = np.zeros((2, 3))
    hand = d.body("gripper")
    rotation = hand.xmat.reshape(3, 3)
    for index, contact in enumerate(d.contact):
        bodies = [int(m.geom_bodyid[g]) for g in contact.geom]
        if source_id not in bodies:
            continue
        other = bodies[1] if bodies[0] == source_id else bodies[0]
        if other not in jaw_ids:
            continue
        # Palm/motor contact is not a pinch between the finger tips.
        if (rotation.T @ (contact.pos - hand.xpos))[2] > -0.075:
            continue
        wrench = np.zeros(6)
        mujoco.mj_contactForce(m, d, index, wrench)
        if wrench[0] <= 0:
            continue
        side = jaw_ids.index(other)
        forces[side] += wrench[0]
        normal = contact.frame[:3] * (1 if bodies[1] == source_id else -1)
        normals[side] += wrench[0] * normal
        result["maxPenetration"] = max(result["maxPenetration"], -float(contact.dist))
    lengths = np.linalg.norm(normals, axis=1)
    opposing = bool(
        np.all(lengths > 1e-6)
        and np.dot(normals[0], normals[1]) / np.prod(lengths) < -0.5
    )
    result.update(
        leftForce=float(forces[0]),
        rightForce=float(forces[1]),
        opposing=opposing,
        secure=bool(
            opposing and np.all(forces > 0.02) and result["maxPenetration"] < 0.0015
        ),
    )
    return result
