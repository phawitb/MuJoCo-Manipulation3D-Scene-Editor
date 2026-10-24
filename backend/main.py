"""Local scene service: shared session IDs across browser, HTTP and MCP."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Literal
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlparse
import mujoco
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Request,
    HTTPException,
    Query,
)
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from .schema import Scene, ASSETS
from .simulation import compiled_meshes
from .sessions import Registry, Command, Conflict
from .importer import import_object, MAX_UPLOAD, MAX_SCENE


@asynccontextmanager
async def lifespan(app):
    app.state.sessions = Registry()
    app.state.render_slots = asyncio.Semaphore(2)
    yield
    await app.state.sessions.close()


app = FastAPI(title="SO-101 Scene Studio", version="3.0.0", lifespan=lifespan)
LOCAL = ("localhost", "127.0.0.1", "::1", "testserver")


def allowed(origin):
    return not origin or urlparse(origin).hostname in LOCAL


@app.middleware("http")
async def local_access(request: Request, call_next):
    if request.url.hostname not in LOCAL or not allowed(
        request.headers.get("origin", "")
    ):
        return JSONResponse({"detail": "Local clients only"}, status_code=403)
    return await call_next(request)


async def bounded_body(request, limit):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, "Payload is too large")
    return bytes(body)


@app.exception_handler(Conflict)
async def conflict_handler(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(ValueError)
async def value_handler(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


def session(request, sid):
    try:
        return request.app.state.sessions.get(sid)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/health")
def health():
    return dict(status="ok", engine="MuJoCo", version=mujoco.__version__, apiVersion=3)


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


@app.get("/api/scene-schema")
def scene_schema():
    return Scene.model_json_schema()


@app.get("/api/command-schema")
def command_schema():
    return Command.model_json_schema()


@app.get("/api/examples")
def examples():
    from .examples import example_catalog

    return example_catalog()


@app.get("/api/sessions")
def list_sessions(request: Request):
    return [
        dict(
            sessionId=s.id,
            name=s.sim.scene.name,
            running=s.sim.running,
            revision=s.sim.revision,
            viewers=len(s.subscribers),
        )
        for s in request.app.state.sessions.items.values()
    ]


@app.post("/api/sessions")
async def create_session(request: Request):
    s = await request.app.state.sessions.create()
    return await asyncio.to_thread(s.packet)


@app.get("/api/sessions/{sid}")
async def read_session(sid: str, request: Request):
    return await asyncio.to_thread(session(request, sid).packet)


@app.get("/api/sessions/{sid}/image")
async def camera_image(
    sid: str, request: Request, view: Literal["main", "top", "front", "wrist"] = "wrist"
):
    state = await asyncio.to_thread(session(request, sid).packet)
    payload = json.dumps(
        {"scene": state["scene"], "joints": state["joints"], "view": view}
    ).encode()
    async with request.app.state.render_slots:
        try:
            process = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-m", "backend.render"],
                input=payload,
                capture_output=True,
                timeout=20,
                cwd=Path(__file__).resolve().parents[1],
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(503, "Camera rendering timed out") from exc
    if process.returncode or not process.stdout.startswith(b"\x89PNG"):
        raise HTTPException(
            503,
            "Native camera renderer unavailable on this host; browser camera views remain available",
        )
    return Response(
        process.stdout,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "X-Scene-Revision": str(state["revision"]),
            "X-Simulation-Time": str(state["time"]),
        },
    )


@app.delete("/api/sessions/{sid}")
async def delete_session(sid: str, request: Request):
    session(request, sid)
    await request.app.state.sessions.delete(sid)
    return {"deleted": sid}


@app.post(
    "/api/sessions/{sid}/command",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": Command.model_json_schema()}},
        }
    },
)
async def command(sid: str, request: Request):
    s = session(request, sid)
    cmd = Command.model_validate_json(await bounded_body(request, MAX_SCENE))
    packet = await asyncio.to_thread(s.execute, cmd)
    s.broadcast(packet)
    return packet


@app.post(
    "/api/import",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def upload(
    request: Request,
    filename: str = Query(max_length=200),
    size: float = Query(default=0.1, ge=0.005, le=1),
):
    data = await bounded_body(request, MAX_UPLOAD)
    obj = await asyncio.to_thread(import_object, data, filename, size)
    return obj.model_dump()


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    if ws.url.hostname not in LOCAL or not allowed(ws.headers.get("origin", "")):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        sid = ws.query_params.get("session")
        s = (
            ws.app.state.sessions.get(sid)
            if sid
            else await ws.app.state.sessions.create(ephemeral=True)
        )
    except (KeyError, ValueError) as exc:
        await ws.send_json(
            {"type": "error", "message": str(exc), "code": "session_missing"}
        )
        await ws.close(code=1008)
        return
    queue = asyncio.Queue(maxsize=3)
    s.subscribers.add(queue)
    await ws.send_json(await asyncio.to_thread(s.packet))
    pending = asyncio.create_task(ws.receive_text())
    updates = asyncio.create_task(queue.get())
    try:
        while True:
            done, _ = await asyncio.wait(
                {pending, updates}, return_when=asyncio.FIRST_COMPLETED
            )
            if updates in done:
                packet = updates.result()
                await ws.send_json(packet)
                if packet.get("type") == "closed":
                    await ws.close(code=1000)
                    break
                updates = asyncio.create_task(queue.get())
            if pending in done:
                raw = pending.result()
                pending = asyncio.create_task(ws.receive_text())
                request_id = None
                try:
                    if len(raw.encode()) > MAX_SCENE:
                        raise ValueError("Scene message exceeds 8 MB")
                    value = json.loads(raw)
                    if not isinstance(value, dict):
                        raise ValueError("Command must be an object")
                    request_id = value.get("requestId")
                    cmd = Command.model_validate(value)
                    packet = await asyncio.to_thread(s.execute, cmd)
                    s.broadcast(packet, exclude=queue)
                    await ws.send_json({**packet, "requestId": request_id})
                except (ValueError, TypeError, ValidationError) as exc:
                    await ws.send_json(
                        dict(
                            type="error",
                            message=str(exc),
                            requestId=request_id,
                            revision=s.sim.revision,
                        )
                    )
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        pass
    finally:
        s.subscribers.discard(queue)
        pending.cancel()
        updates.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(pending, updates, return_exceptions=True)
