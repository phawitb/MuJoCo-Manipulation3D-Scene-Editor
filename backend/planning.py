"""Bounded, isolated physics rehearsal. A successful plan never edits live state."""

import copy
import hashlib
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import mujoco
import numpy as np

EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scene-planner")
PLANNING_SLOTS = threading.BoundedSemaphore(4)


def idle_plan(message="Choose pick and place objects, then calculate a path."):
    return dict(status="idle", points=[], duration=0.0, message=message, verified=False)


def clone_simulation(sim):
    from .simulation import Simulation
    from .policy import PickPlacePolicy

    clone = Simulation.__new__(Simulation)
    clone.scene = sim.scene.model_copy(deep=True)
    clone.model = copy.copy(sim.model)
    clone.data = mujoco.MjData(clone.model)
    mujoco.mj_copyData(clone.data, clone.model, sim.data)
    clone.object_bodies = sim.object_bodies.copy()
    clone.visible_ids = list(sim.visible_ids)
    clone.revision = sim.revision
    clone.running = False
    clone.policy = PickPlacePolicy(clone)
    return clone


def physics_fingerprint(sim):
    kind = mujoco.mjtState.mjSTATE_INTEGRATION
    values = np.empty(mujoco.mj_stateSize(sim.model, kind))
    mujoco.mj_getState(sim.model, sim.data, values, kind)
    scene = sim.scene.model_dump(exclude={"cameras", "name"})
    return hashlib.sha256(
        json.dumps(scene, sort_keys=True).encode()
        + values.tobytes()
        + sim.model.eq_data.tobytes()
    ).hexdigest()


def unwanted_contact(sim):
    objects = sim.object_bodies
    source = objects.get(sim.policy.source)
    target = objects.get(sim.policy.target)
    other = set(objects.values()) - {source, target}
    robot = set(range(1, sim.model.nbody)) - set(objects.values())
    for contact in sim.data.contact:
        if contact.dist > -0.004:
            continue
        a, b = (int(sim.model.geom_bodyid[g]) for g in contact.geom)
        if (a in other and (b in robot or (b == source and sim.policy.held))) or (
            b in other and (a in robot or (a == source and sim.policy.held))
        ):
            return "Path meets another object. Move the obstruction or reposition the task."
        if (a in robot and b == 0) or (b in robot and a == 0):
            return "Arm path intersects the table. Move the task closer or adjust its position."
    return None


def calculate_plan(sim, cancel=None):
    cancel = cancel or threading.Event()
    started = time.monotonic()
    configurations = [
        {},
        {"lift": 0.08, "transfer_clearance": 0.10},
        {"lift": 0.12, "transfer_clearance": 0.15},
        {"lift": 0.09, "yaw_offset": 0.35},
        {"lift": 0.09, "yaw_offset": -0.35},
    ]
    failures = []
    for configuration in configurations:
        if cancel.is_set():
            return idle_plan("Calculation cancelled.")
        if time.monotonic() - started > 45:
            failures.append(
                "Calculation time limit reached. Simplify the scene and try again."
            )
            break
        trial = clone_simulation(sim)
        trial.policy.configuration = configuration
        points = [trial.data.site("gripperframe").xpos.tolist()]
        start = float(trial.data.time)
        max_z = (
            float(trial.data.body("object_" + trial.scene.task.source).xpos[2])
            if trial.scene.task.source
            else 0.0
        )
        try:
            trial.start_policy()
            for step in range(1500):
                if cancel.is_set():
                    return idle_plan("Calculation cancelled.")
                if time.monotonic() - started > 45:
                    raise ValueError(
                        "Calculation time limit reached. Simplify the scene and try again."
                    )
                trial.step(10)
                max_z = max(
                    max_z,
                    float(trial.data.xpos[trial.object_bodies[trial.policy.source], 2]),
                )
                if step % 5 == 0:
                    points.append(trial.data.site("gripperframe").xpos.tolist())
                collision = unwanted_contact(trial)
                if collision:
                    raise ValueError(collision)
                if trial.policy.status in ("failed", "succeeded"):
                    break
            if not trial.policy.success:
                raise ValueError(trial.policy.message)
            points.append(trial.data.site("gripperframe").xpos.tolist())
            return dict(
                status="ready",
                id=physics_fingerprint(sim)[:16],
                points=points,
                duration=float(trial.data.time) - start,
                message="Rehearsal succeeded. Inspect the rainbow path, then Run simulation.",
                verified=True,
                configuration=configuration,
                fingerprint=physics_fingerprint(sim),
                maxSourceHeight=max_z,
                attempts=len(failures) + 1,
            )
        except ValueError as exc:
            failures.append(str(exc))
    return dict(
        status="failed",
        points=[],
        duration=0.0,
        message=failures[-1] if failures else "No valid path found.",
        verified=False,
        attempts=len(failures),
    )
