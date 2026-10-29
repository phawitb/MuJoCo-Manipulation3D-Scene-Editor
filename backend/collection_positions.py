"""Seeded planar task placement; preserve contained objects and table bounds."""

import math
import random
import mujoco
import numpy as np
from .catalog import profile
from .contents import inside_container_geometry


def object_rotation(obj):
    rotation = np.empty(9)
    mujoco.mju_quat2Mat(rotation, np.array(obj.quaternion, dtype=float))
    return rotation.reshape(3, 3)


def object_half_extent(obj):
    return np.abs(object_rotation(obj)) @ (
        np.array(profile(obj)["dimensions"]) * obj.scale / 2
    )


def randomize_positions(scene, radius, seed):
    objects = {o.id: o for o in scene.objects}
    if not scene.task.source or not scene.task.target:
        return
    parents = {key: key for key in objects}

    def root(key):
        while parents[key] != key:
            key = parents[key]
        return key

    # Match the controller's local-space containment, including lower-half
    # cargo and spoon endpoints, without introducing any physical attachment.
    for vessel in objects.values():
        if profile(vessel)["family"] not in ("cup", "bowl"):
            continue
        for obj in objects.values():
            if obj.id != vessel.id and inside_container_geometry(
                vessel,
                obj,
                np.array(vessel.position),
                object_rotation(vessel),
                np.array(obj.position),
                object_rotation(obj),
            ):
                parents[root(obj.id)] = root(vessel.id)
    selected = [scene.task.source, scene.task.target]
    if root(selected[0]) == root(selected[1]):
        raise ValueError(
            "Pick and destination share a placement group; separate them or turn off position randomization"
        )
    for selected_id in selected:
        group = [obj for obj in objects.values() if root(obj.id) == root(selected_id)]
        rng = random.Random(f"collection-v1:{seed}:position:{selected_id}")
        for _ in range(128):
            angle, length = (
                rng.uniform(0, 2 * math.pi),
                radius * math.sqrt(rng.random()),
            )
            offset = np.array([math.cos(angle), math.sin(angle)]) * length
            if all(
                np.all(
                    np.abs(np.array(obj.position[:2]) + offset)
                    + object_half_extent(obj)[:2]
                    <= np.array([scene.table.width, scene.table.depth]) / 2 - 0.005
                )
                for obj in group
            ):
                for obj in group:
                    obj.position[:2] = (np.array(obj.position[:2]) + offset).tolist()
                break
        else:
            raise ValueError(
                "No randomized placement fits the table; move the task inward or reduce its size"
            )
