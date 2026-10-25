"""UI and MCP share this injectable, off-event-loop command surface."""

import asyncio
from fastapi import APIRouter, HTTPException, Request, Path
from fastapi.responses import Response
from .schemas import Connect, Owner, Calibration, Jog, Sync, Scan, Assignments
from .service import ConnectionError
from .driver import discover_ports


def create_router(service=None):
    router = APIRouter(prefix="/api/connection", tags=["connection"])

    def get(request):
        return service if service is not None else request.app.state.connection

    async def invoke(fn, *args):
        try:
            return await asyncio.to_thread(fn, *args)
        except ConnectionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(503, str(exc)) from exc

    @router.get("/status")
    async def status(request: Request):
        return await invoke(get(request).status)

    @router.get("/ports")
    async def ports():
        return await invoke(discover_ports)

    @router.get("/settings")
    async def settings(request: Request):
        return await invoke(get(request).settings)

    @router.post("/connect")
    async def connect(body: Connect, request: Request):
        return await invoke(
            get(request).connect, body.port, body.session_id, request.app.state.sessions
        )

    @router.post("/disconnect")
    async def disconnect(body: Owner, request: Request):
        return await invoke(get(request).disconnect, body.session_id)

    @router.post("/enable")
    async def enable(body: Owner, request: Request):
        return await invoke(get(request).enable, body.session_id)

    @router.post("/align")
    async def align(body: Owner, request: Request):
        return await invoke(get(request).align, body.session_id)

    @router.post("/stop")
    async def stop(body: Owner, request: Request):
        return await invoke(get(request).stop, body.session_id)

    @router.post("/heartbeat")
    async def heartbeat(body: Owner, request: Request):
        return await invoke(get(request).heartbeat, body.session_id)

    @router.put("/calibration")
    async def calibration(body: Calibration, request: Request):
        return await invoke(get(request).save_calibration, body)

    @router.post("/jog")
    async def jog(body: Jog, request: Request):
        return await invoke(
            get(request).jog, body.session_id, body.joint, body.delta_rad
        )

    @router.post("/sync")
    async def sync(body: Sync, request: Request):
        return await invoke(get(request).sync, body.session_id, body.mode)

    @router.post("/cameras/scan")
    async def scan(body: Scan, request: Request):
        s = get(request)
        return dict(
            cameras=await invoke(s.cameras.scan, body.max_index),
            assignments=s.settings()["assignments"],
        )

    @router.put("/cameras/assignments")
    async def assignments(body: Assignments, request: Request):
        return await invoke(get(request).assign_cameras, body.model_dump())

    @router.get("/cameras/{index}/frame")
    async def frame(request: Request, index: int = Path(ge=0, le=7)):
        return Response(
            await invoke(get(request).cameras.frame, index),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    return router
