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
    scene = sim.scene.model_dump(exclude={"cameras", "name", "appearance"})
    scene["table"].pop("color", None)
    for obj in scene["objects"]:
        obj.pop("color", None)
    return hashlib.sha256(
        json.dumps(scene, sort_keys=True).encode()
        + values.tobytes()
        + sim.model.eq_data.tobytes()
    ).hexdigest()


def unwanted_contact(sim):
    from .safety import collision_issue, joint_issue

    return collision_issue(sim) or joint_issue(sim)


def initial_overlap(sim):
    """A path cannot repair solids that already overlap at its starting state."""
    from .safety import collision_issue, joint_issue

    joint = joint_issue(sim)
    if joint:
        return joint
    issue = collision_issue(sim)
    if issue:
        return (
            "Starting pose overlaps: "
            + issue.split(": ", 1)[-1]
            + " Move the object or adjust SO-101 Joint positions before calculating. "
            "Save the corrected reset pose if needed."
        )
    return None


def calculate_plan(sim, cancel=None):
    cancel = cancel or threading.Event()
    if cancel.is_set():
        return idle_plan("Calculation cancelled.")
    overlap = initial_overlap(sim)
    if overlap:
        return dict(
            status="failed",
            points=[],
            duration=0.0,
            message=overlap,
            verified=False,
            attempts=0,
        )
    started = time.monotonic()
    configurations = [
        {},
        {"lift": 0.08, "transfer_clearance": 0.10},
        {"lift": 0.12, "transfer_clearance": 0.15},
        {"reverse_grasp": True},
        {"reverse_grasp": True, "lift": 0.08, "transfer_clearance": 0.10},
        {"grasp_along_offset": 0.03},
        {"grasp_along_offset": 0.03, "reverse_grasp": True},
    ]
    from .catalog import profile

    source = next((o for o in sim.scene.objects if o.id == sim.scene.task.source), None)
    if source is not None and source.asset in ("mesh", "mujoco"):
        # Tall imports on tall receivers may have valid low-clearance transfers
        # beyond the existing high-lift candidates. Physical rehearsal remains
        # authoritative for contact, collision, settling and withdrawal.
        configurations.extend(
            [
                {"lift": 0.08, "transfer_clearance": 0.035},
                {"reverse_grasp": True, "lift": 0.08, "transfer_clearance": 0.035},
            ]
        )
    if source is not None and profile(source)["family"] == "cup":
        configurations = [
            dict(rim_angle=angle)
            for angle in (0, np.pi / 4, -np.pi / 4, np.pi / 2, -np.pi / 2, np.pi)
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
        # Reserve another 2 mm for position uncertainty during rehearsal. This
        # changes acceptance only, not the trajectory; execution still enforces
        # the physical 4 mm pre-closing clearance on the measured state.
        from .grasp import CUP_MIN_CLEARANCE, CUP_POSITION_RESERVE

        trial.policy.minimum_approach_clearance = (
            CUP_MIN_CLEARANCE + CUP_POSITION_RESERVE
        )
        points = [trial.data.site("gripperframe").xpos.tolist()]
        start = float(trial.data.time)
        max_z = (
            float(trial.data.body("object_" + trial.scene.task.source).xpos[2])
            if trial.scene.task.source
            else 0.0
        )
        try:
            trial.start_policy()
            for step in range(int(30 / (10 * trial.model.opt.timestep))):
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
