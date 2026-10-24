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


class Conflict(ValueError):
    pass


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    type: Literal[
        "load",
        "reset",
        "example",
        "run",
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
    camera: Literal["main", "top", "front"] | None = None
    value: dict | None = None
    count: int = Field(default=10, ge=1, le=2500)


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

    def packet(self, snapshot=True):
        with self.lock:
            p = self.sim.snapshot() if snapshot else self.sim.state()
            p.update(sessionId=self.id, sequence=self.sequence, mode=self.mode)
            return p

    def execute(self, cmd: Command):
        with self.lock:
            self.touched = time.monotonic()
            s = self.sim
            kind = cmd.type
            editing = kind in (
                "load",
                "example",
                "task",
                "object_add",
                "object_update",
                "object_remove",
                "robot",
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
                s.load(Scene(cameras=s.scene.cameras))
            elif kind == "example":
                scene = example_scene()
                scene.cameras = s.scene.cameras
                s.load(scene)
            elif kind == "run":
                s.start_policy()
                self.mode = "policy"
            elif kind == "pause":
                s.running = False
            elif kind == "stop":
                s.stop_policy()
            elif kind == "physics":
                s.stop_policy()
                s.running = True
                self.mode = "physics"
            elif kind == "step":
                if s.running:
                    raise ValueError("Pause before stepping")
                s.step(cmd.count)
            elif kind == "task":
                scene = s.export_scene()
                scene.task = Task(source=cmd.source, target=cmd.target)
                s.load(Scene.model_validate(scene.model_dump()))
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
                    raise ValueError("Choose main, top or front camera")
                scene = s.export_scene()
                scene.cameras[cmd.camera] = Camera.model_validate(cmd.value)
                scene = Scene.model_validate(scene.model_dump())
                s.scene.cameras = scene.cameras
                s.revision += 1
            self.sequence += 1
            return self.packet()

    def broadcast(self, packet):
        for queue in self.subscribers.copy():
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(packet)

    def tick(self, count):
        with self.lock:
            if not self.sim.running:
                return None
            try:
                self.sim.step(count)
                self.sequence += 1
                return self.packet(snapshot=not self.sim.running)
            except ValueError as exc:
                self.sim.stop_policy()
                self.sim.policy.fail(str(exc))
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
            if self.sim.running:
                accum += min(now - last, 0.1)
                count = min(int(accum / 0.002), 50)
                if count:
                    packet = await asyncio.to_thread(self.tick, count)
                    accum -= count * 0.002
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
        s.runner.cancel()
        await asyncio.gather(s.runner, return_exceptions=True)
        await asyncio.to_thread(s.sim.stop_policy)
        s.broadcast({"type": "closed", "sessionId": sid})
        del self.items[sid]

    async def close(self):
        for sid in list(self.items):
            await self.delete(sid)
