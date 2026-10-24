"""Local modular application shell. Feature code lives under backend/modules."""

import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .http import LOCAL, allowed
from .sessions import Registry, Conflict

MODULES = ("gym", "connection", "blender")


def create_app(modules=None):
    config = (
        modules
        if modules is not None
        else os.environ.get("SO101_MODULES", ",".join(MODULES))
    )
    enabled = [name for name in MODULES if name in config.split(",")]
    if not enabled:
        raise ValueError(
            "No studio modules enabled; use SO101_MODULES=gym,connection,blender"
        )

    @asynccontextmanager
    async def lifespan(application):
        application.state.sessions = Registry()
        application.state.render_slots = asyncio.Semaphore(2)
        if "connection" in enabled:
            from .modules.connection.service import ConnectionService

            application.state.connection = ConnectionService()
        try:
            yield
        finally:
            if "connection" in enabled:
                await asyncio.to_thread(application.state.connection.shutdown)
            await application.state.sessions.close()

    app = FastAPI(title="SO-101 Scene Studio", version="4.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        if request.url.hostname not in LOCAL or not allowed(
            request.headers.get("origin", "")
        ):
            return JSONResponse({"detail": "Local clients only"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/modules")
    def modules_contract():
        return {"enabled": enabled, "available": list(MODULES), "version": 4}

    # Scene sessions are a shared engine contract even in a device-only build.
    from .modules.gym.routes import router as gym_router

    app.include_router(gym_router)
    if "connection" in enabled:
        from .modules.connection.routes import create_router

        app.include_router(create_router())
    if "blender" in enabled:
        from .modules.blender.routes import router as blender_router

        app.include_router(blender_router)
    return app


app = create_app()
