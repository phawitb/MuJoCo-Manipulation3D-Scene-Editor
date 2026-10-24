"""Shared bounded local HTTP helpers."""

from urllib.parse import urlparse
from fastapi import HTTPException

LOCAL = ("localhost", "127.0.0.1", "::1", "testserver")


def allowed(origin):
    return not origin or urlparse(origin).hostname in LOCAL


async def bounded_body(request, limit):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, "Payload is too large")
    return bytes(body)


def session(request, sid):
    try:
        return request.app.state.sessions.get(sid)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
