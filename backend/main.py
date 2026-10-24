"""Local editor API. Each connection has its own isolated MuJoCo session."""

import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import mujoco
from .schema import Scene, ASSETS
from .simulation import Simulation, compiled_meshes

app = FastAPI(title="SO-101 Scene Studio", version="1.0.0")


@app.get("/api/health")
def health():
    return dict(status="ok", engine="MuJoCo", version=mujoco.__version__)


@app.get("/api/assets")
def assets():
    return ASSETS


@app.get("/api/default-scene")
def default_scene():
    return Scene().model_dump()


@app.get("/api/meshes")
def meshes():
    return JSONResponse(
        compiled_meshes(), headers={"Cache-Control": "public, max-age=3600"}
    )


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    # Local-only service; prevent websites from controlling a localhost session.
    origin = ws.headers.get("origin", "")
    from urllib.parse import urlparse

    if origin and urlparse(origin).hostname not in (
        "localhost",
        "127.0.0.1",
        "[::1]",
        "::1",
    ):
        await ws.close(code=1008)
        return
    await ws.accept()
    sim = await asyncio.to_thread(Simulation)
    await ws.send_json(sim.snapshot())
    pending = asyncio.create_task(ws.receive_text())
    last_tick = time.monotonic()
    accumulated = 0.0
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=1 / 30)
            if pending in done:
                raw = pending.result()
                pending = asyncio.create_task(ws.receive_text())
                request_id = None
                try:
                    if len(raw) > 150_000:
                        raise ValueError("Scene message exceeds 150 KB")
                    cmd = json.loads(raw)
                    if not isinstance(cmd, dict):
                        raise ValueError("Command must be an object")
                    request_id = cmd.get("requestId")
                    kind = cmd.get("type")
                    if kind == "load":
                        if sim.running:
                            raise ValueError("Pause simulation before editing")
                        if cmd.get("revision", sim.revision) != sim.revision:
                            raise ValueError(
                                "Stale scene revision; retry after latest snapshot"
                            )
                        scene = Scene.model_validate(cmd.get("scene"))
                        await asyncio.to_thread(sim.load, scene)
                        packet = sim.snapshot()
                    elif kind == "reset":
                        await asyncio.to_thread(sim.load, Scene())
                        packet = sim.snapshot()
                    elif kind == "run":
                        sim.running = True
                        accumulated = 0
                        packet = sim.state()
                    elif kind == "pause":
                        sim.running = False
                        packet = sim.snapshot()
                    elif kind == "step":
                        if sim.running:
                            raise ValueError("Pause before stepping")
                        await asyncio.to_thread(sim.step, 10)
                        packet = sim.state()
                    elif kind == "snapshot":
                        packet = sim.snapshot()
                    else:
                        raise ValueError(
                            "Unknown command; use load, reset, run, pause, step, or snapshot"
                        )
                    packet["requestId"] = request_id
                    await ws.send_json(packet)
                    last_tick = time.monotonic()
                except (ValueError, TypeError, ValidationError) as exc:
                    await ws.send_json(
                        dict(
                            type="error",
                            message=str(exc),
                            requestId=request_id,
                            revision=sim.revision,
                        )
                    )
            now = time.monotonic()
            if sim.running:
                accumulated += min(now - last_tick, 0.1)
                count = min(int(accumulated / 0.002), 50)
                if count:
                    try:
                        await asyncio.to_thread(sim.step, count)
                        accumulated -= count * 0.002
                        await ws.send_json(sim.state())
                    except ValueError as exc:
                        await ws.send_json(sim.snapshot())
                        await ws.send_json(
                            dict(type="error", message=str(exc), revision=sim.revision)
                        )
            last_tick = now
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        sim.running = False
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
