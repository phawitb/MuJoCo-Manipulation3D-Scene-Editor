"""One serialized command surface for the UI, REST clients and MCP bridge."""

import asyncio
import time
import threading
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Any
from .schema import Scene, SceneObject, Task, Camera
from .simulation import Simulation
from .examples import example_scene
from .planning import (
    EXECUTOR,
    PLANNING_SLOTS,
    idle_plan,
    clone_simulation,
    calculate_plan,
    physics_fingerprint,
)


class Conflict(ValueError):
    pass


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    type: Literal[
        "load",
        "reset",
        "example",
        "run",
        "plan",
        "pause",
        "stop",
        "physics",
        "step",
        "snapshot",
        "task",
        "object_add",
        "object_update",
        "object_remove",
        "robot",
        "camera",
    ]
    requestId: str | None = Field(default=None, max_length=100)
    revision: int | None = Field(default=None, ge=0)
    scene: dict | None = None
    source: str | None = None
    target: str | None = None
    object: dict | None = None
    id: str | None = None
    patch: dict[str, Any] | None = None
    joints: list[float] | None = None
    camera: Literal["main", "top", "front", "back"] | None = None
    value: dict | None = None
    count: int = Field(default=10, ge=1, le=2500)
    exampleId: str | None = Field(default=None, max_length=80)


class Session:
    def __init__(self, ephemeral=False):
        self.ephemeral = ephemeral
        self.id = uuid4().hex
        self.sim = Simulation()
        self.lock = threading.RLock()
        self.subscribers = set()
        self.touched = time.monotonic()
        self.sequence = 0
        self.mode = "policy"
        self.closed = False
        self.runner = None
        self.plan = idle_plan()
        self.plan_future = None
        self.plan_cancel = threading.Event()
        self.plan_dirty = False

    def invalidate_plan(self):
        self.plan_cancel.set()
        if self.plan_future:
            self.plan_future.cancel()
        self.plan_future = None
        self.plan = idle_plan("Scene changed. Calculate a new path before running.")

    def collect_plan(self):
        if self.plan_future and self.plan_future.done():
            future, self.plan_future = self.plan_future, None
            try:
                result = future.result()
                if result.get("fingerprint") and result[
                    "fingerprint"
                ] != physics_fingerprint(self.sim):
                    self.invalidate_plan()
                else:
                    self.plan = result
            except Exception:
                self.plan = {
                    **idle_plan(
                        "Calculation failed. Simplify the scene and try again."
                    ),
                    "status": "failed",
                }
            self.sequence += 1
            self.plan_dirty = True

    def packet(self, snapshot=True):
        with self.lock:
            self.collect_plan()
            p = self.sim.snapshot() if snapshot else self.sim.state()
            p.update(sessionId=self.id, sequence=self.sequence, mode=self.mode)
            p["plan"] = {
                k: v
                for k, v in self.plan.items()
                if k not in ("configuration", "fingerprint")
            }
            return p

    def execute(self, cmd: Command):
        with self.lock:
            self.touched = time.monotonic()
            s = self.sim
            kind = cmd.type
            self.collect_plan()
            editing = kind in (
                "load",
                "example",
                "task",
                "object_add",
                "object_update",
                "object_remove",
                "robot",
                "plan",
            )
            if editing and s.running:
                raise ValueError("Pause simulation before editing")
            if (
                kind
                in (
                    "load",
                    "task",
                    "object_add",
                    "object_update",
                    "object_remove",
                    "robot",
                    "camera",
                )
                and cmd.revision is not None
                and cmd.revision != s.revision
            ):
                raise Conflict("Stale scene revision; retry after latest snapshot")
            if kind == "load":
                s.load(Scene.model_validate(cmd.scene))
            elif kind == "reset":
                scene = Scene(cameras=s.scene.cameras)
                scene.robot.reset_joints = list(s.scene.robot.reset_joints)
                scene.robot.joints = list(scene.robot.reset_joints)
                s.load(scene)
            elif kind == "example":
                scene = (
                    example_scene(cmd.exampleId) if cmd.exampleId else example_scene()
                )
                scene.cameras = s.scene.cameras
                scene.robot.reset_joints = list(s.scene.robot.reset_joints)
                scene.robot.joints = list(scene.robot.reset_joints)
                s.load(scene)
            elif kind == "plan":
                if s.policy.status == "running":
                    raise ValueError(
                        "Stop the paused task before calculating a new path."
                    )
                if self.plan_future:
                    return self.packet()
                if not PLANNING_SLOTS.acquire(blocking=False):
                    raise ValueError(
                        "Planner is busy. Wait for another calculation to finish, then try again."
                    )
                self.plan_cancel = threading.Event()
                try:
                    captured = clone_simulation(s)
                    self.plan = {
                        **idle_plan("Rehearsing the task in an isolated simulation…"),
                        "status": "calculating",
                    }
                    self.plan_future = EXECUTOR.submit(
                        calculate_plan, captured, self.plan_cancel
                    )
                    self.plan_future.add_done_callback(
                        lambda _: PLANNING_SLOTS.release()
                    )
                except Exception:
                    PLANNING_SLOTS.release()
                    raise
            elif kind == "run":
                if s.policy.status != "running":
                    if not self.plan.get("verified") or self.plan.get(
                        "fingerprint"
                    ) != physics_fingerprint(s):
                        self.invalidate_plan()
                        raise ValueError(
                            "Calculate a successful path for this scene before running."
                        )
                    s.policy.configuration = self.plan["configuration"]
                s.start_policy()
                self.mode = "policy"
            elif kind == "pause":
                s.running = False
            elif kind == "stop":
                self.invalidate_plan()
                s.stop_policy()
            elif kind == "physics":
                self.invalidate_plan()
                s.stop_policy()
                s.running = True
                self.mode = "physics"
            elif kind == "step":
                if s.running:
                    raise ValueError("Pause before stepping")
                self.invalidate_plan()
                s.step(cmd.count)
            elif kind == "task":
                scene = s.scene.model_copy(deep=True)
                scene.task = Task(source=cmd.source, target=cmd.target)
                scene = Scene.model_validate(scene.model_dump())
                # Instruction edits do not alter positions, velocities or targets.
                from .policy import PickPlacePolicy

                s.scene.task = scene.task
                s.policy = PickPlacePolicy(s)
                s.revision += 1
            elif kind in ("object_add", "object_update", "object_remove", "robot"):
                scene = s.export_scene()
                if kind == "object_add":
                    scene.objects.append(SceneObject.model_validate(cmd.object))
                elif kind == "robot":
                    patch = cmd.patch or {}
                    if cmd.joints is not None:
                        patch = {**patch, "joints": cmd.joints}
                    scene.robot = scene.robot.model_copy(update=patch)
                else:
                    obj = next((o for o in scene.objects if o.id == cmd.id), None)
                    if obj is None:
                        raise ValueError("Object does not exist")
                    if kind == "object_remove":
                        scene.objects.remove(obj)
                        if scene.task.source == cmd.id:
                            scene.task.source = None
                        if scene.task.target == cmd.id:
                            scene.task.target = None
                    else:
                        if "id" in (cmd.patch or {}):
                            raise ValueError("Object ID cannot be changed")
                        scene.objects[scene.objects.index(obj)] = obj.model_copy(
                            update=cmd.patch or {}
                        )
                s.load(Scene.model_validate(scene.model_dump()))
            elif kind == "camera":
                if cmd.camera is None:
                    raise ValueError("Choose main, top, front or back camera")
                scene = s.export_scene()
                scene.cameras[cmd.camera] = Camera.model_validate(cmd.value)
                scene = Scene.model_validate(scene.model_dump())
                s.scene.cameras = scene.cameras
                s.revision += 1
            if editing and kind != "plan" or kind == "reset":
                self.invalidate_plan()
            self.sequence += 1
            return self.packet()

    def broadcast(self, packet, exclude=None):
        for queue in self.subscribers.copy():
            if queue is exclude:
                continue
            # Coalesce replaceable frames, retaining the latest full structure.
            # A slow viewer needs both that snapshot and the freshest poses.
            packets = [packet]
            while not queue.empty():
                packets.append(queue.get_nowait())
            closed = next((p for p in packets if p["type"] == "closed"), None)
            if closed:
                queue.put_nowait(closed)
                continue
            snapshots = [p for p in packets if p["type"] == "snapshot"]
            latest = max(packets, key=lambda p: p["sequence"])
            snapshot = (
                max(snapshots, key=lambda p: p["sequence"]) if snapshots else None
            )
            if snapshot:
                queue.put_nowait(snapshot)
            if latest is not snapshot:
                queue.put_nowait(latest)

    def tick(self, count):
        with self.lock:
            if not self.sim.running:
                return None
            try:
                self.sim.step(count)
                if not self.sim.running:
                    self.plan.update(
                        status="idle",
                        verified=False,
                        message="Task finished. Calculate again before a new run.",
                    )
                self.sequence += 1
                return self.packet(snapshot=not self.sim.running)
            except ValueError as exc:
                self.sim.stop_policy()
                self.sim.policy.fail(str(exc))
                # Numerical/workspace guards must pause immediately; only an
                # ordinary dropped grasp receives the passive settling period.
                self.sim.policy.failure_settle_until = None
                self.sim.running = False
                self.sequence += 1
                p = self.packet()
                p["warning"] = str(exc)
                return p

    async def loop(self):
        last = time.monotonic()
        accum = 0.0
        while not self.closed:
            await asyncio.sleep(1 / 30)
            now = time.monotonic()
            with self.lock:
                self.collect_plan()
                if self.plan_dirty:
                    self.plan_dirty = False
                    self.broadcast(self.packet())
            if self.sim.running:
                accum += min(now - last, 0.1)
                dt = self.sim.model.opt.timestep
                count = min(int(accum / dt), int(0.1 / dt))
                if count:
                    packet = await asyncio.to_thread(self.tick, count)
                    accum -= count * dt
                    if packet:
                        self.broadcast(packet)
            else:
                accum = 0.0
            last = now


class Registry:
    def __init__(self):
        self.items = {}
        self.lock = asyncio.Lock()

    async def create(self, ephemeral=False):
        async with self.lock:
            for sid, s in list(self.items.items()):
                if (
                    not s.subscribers
                    and not s.sim.running
                    and time.monotonic() - s.touched > 1800
                ):
                    await self.delete(sid)
            if len(self.items) >= 16:
                unused = sorted(
                    (
                        s
                        for s in self.items.values()
                        if s.ephemeral and not s.subscribers and not s.sim.running
                    ),
                    key=lambda s: s.touched,
                )
                if unused:
                    await self.delete(unused[0].id)
            if len(self.items) >= 16:
                raise ValueError(
                    "16 sessions are already open. Close an unused session first."
                )
            s = await asyncio.to_thread(Session, ephemeral)
            self.items[s.id] = s
            s.runner = asyncio.create_task(s.loop())
            return s

    def get(self, sid):
        if sid not in self.items:
            raise KeyError(
                "Session not found; create a session or use an ID from the editor"
            )
        self.items[sid].touched = time.monotonic()
        return self.items[sid]

    async def delete(self, sid):
        s = self.get(sid)
        s.closed = True
        with s.lock:
            s.invalidate_plan()
        s.runner.cancel()
        await asyncio.gather(s.runner, return_exceptions=True)
        await asyncio.to_thread(s.sim.stop_policy)
        s.broadcast({"type": "closed", "sessionId": sid})
        del self.items[sid]

    async def close(self):
        for sid in list(self.items):
            await self.delete(sid)
