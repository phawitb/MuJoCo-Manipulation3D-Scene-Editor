"""Observe a container's contents through geometry and real contact support."""

import mujoco
import numpy as np

from .catalog import profile


def inside_container(sim, container, obj):
    vessel = sim.data.body(f"object_{container.id}")
    body = sim.data.body(f"object_{obj.id}")
    return inside_container_geometry(
        container,
        obj,
        vessel.xpos,
        vessel.xmat.reshape(3, 3),
        body.xpos,
        body.xmat.reshape(3, 3),
    )


def inside_container_geometry(
    container, obj, vessel_position, vessel_rotation, item_position, item_rotation
):
    """Shared containment predicate for measured physics and initial scene poses."""
    p, item = profile(container), profile(obj)
    # Either end of a spoon can be inside the vessel. Checking only its bowl
    # misses the common handle-first orientation and would silently skip cargo.
    offsets = [np.zeros(3)]
    if item["family"] == "spoon":
        offsets = [
            np.array([x * obj.scale, 0, 0])
            for x in (-item["dimensions"][0] * 0.42, item["grasp"], 0, item["bowl"])
        ]
    for offset in offsets:
        point = item_position + item_rotation @ offset
        relative = vessel_rotation.T @ (point - vessel_position)
        if (
            np.linalg.norm(relative[:2]) < p["rim"] * container.scale
            and -p["dimensions"][2] * container.scale / 2 - 0.003
            < relative[2]
            < p["dimensions"][2] * container.scale / 2 + 0.008
        ):
            return True
    return False


def find_contents(sim, source):
    cup = next(o for o in sim.scene.objects if o.id == source)
    if profile(cup)["family"] != "cup":
        return []
    return [
        o.id
        for o in sim.scene.objects
        if o.id != source and inside_container(sim, cup, o)
    ]


def contents_issue(sim, source, contents, settled=False):
    cup = next(o for o in sim.scene.objects if o.id == source)
    for oid in contents:
        obj = next(o for o in sim.scene.objects if o.id == oid)
        if not inside_container(sim, cup, obj):
            return f"Contents left the cup: {obj.name}. Choose another rim grasp or reduce motion."
        if settled:
            supported = False
            for i, contact in enumerate(sim.data.contact):
                bodies = {int(sim.model.geom_bodyid[g]) for g in contact.geom}
                if bodies == {sim.object_bodies[source], sim.object_bodies[oid]}:
                    wrench = np.zeros(6)
                    mujoco.mj_contactForce(sim.model, sim.data, i, wrench)
                    supported |= wrench[0] > 0.005
            bid = sim.object_bodies[oid]
            dof = sim.model.jnt_dofadr[sim.model.body_jntadr[bid]]
            stable = (
                np.linalg.norm(sim.data.qvel[dof : dof + 3]) < 0.03
                and np.linalg.norm(sim.data.qvel[dof + 3 : dof + 6]) < 0.3
            )
            if not supported or not stable:
                return f"Contents have not settled in the cup: {obj.name}."
    return None
