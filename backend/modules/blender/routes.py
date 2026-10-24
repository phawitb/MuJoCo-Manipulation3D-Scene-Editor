"""Bounded HTTP facade. Heavy image and mesh work runs off the event loop."""

import asyncio
import threading
from fastapi import APIRouter, HTTPException, Request
from .schemas import MAX_REQUEST_BYTES, ReconstructionRequest, ReconstructionResult
from .service import reconstruct

router = APIRouter(prefix="/api/blender", tags=["blender"])
_slots = threading.BoundedSemaphore(2)


def _create(payload):
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "Two images are already processing; try again shortly")
    try:
        return reconstruct(payload)
    finally:
        _slots.release()


@router.post(
    "/create",
    response_model=ReconstructionResult,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ReconstructionRequest.model_json_schema()
                }
            },
        }
    },
)
async def create(request: Request):
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
            raise HTTPException(
                413, "Image request is too large; use a PNG or JPEG under 6 MB"
            )
        body.extend(chunk)
    try:
        payload = ReconstructionRequest.model_validate_json(body)
        return await asyncio.to_thread(_create, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
