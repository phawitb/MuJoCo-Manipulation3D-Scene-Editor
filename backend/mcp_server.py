"""Official MCP SDK stdio bridge. Run with: .venv/bin/python -m backend.mcp_server"""

import base64
import os
from urllib.parse import urlparse
import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ImageContent
from typing import Literal
from .sessions import Command

API = os.environ.get("SO101_API_URL", "http://127.0.0.1:8765").rstrip("/")
if urlparse(API).hostname not in ("localhost", "127.0.0.1", "::1"):
    raise ValueError("SO101_API_URL must address the local editor service")
mcp = MCPServer(
    "SO-101 Scene Studio",
    instructions="Start the editor service first. Call list_sessions and use the explicit sessionId shown in the browser to control that same scene. Create a session for independent headless work. SI meters, Z up, WXYZ quaternions. Read scene and revision before editing. Run executes the selected IK task with disclosed grasp assistance; physics only is a separate command. Poll get_scene to observe completion; never assume command acceptance means task success.",
)


async def request(method, path, **kwargs):
    async with httpx.AsyncClient(base_url=API, timeout=30, trust_env=False) as client:
        response = await client.request(method, path, **kwargs)
        if response.is_error:
            try:
                message = response.json().get("detail", response.text)
            except ValueError:
                message = response.text
            raise ValueError(f"{response.status_code}: {message}")
        return response.json()


def compact(packet):
    return {k: v for k, v in packet.items() if k not in ("geometry", "meshes", "poses")}


@mcp.tool()
async def list_sessions() -> list[dict]:
    """List running editor sessions, IDs, names, viewers and revisions."""
    return await request("GET", "/api/sessions")


@mcp.tool()
async def create_session() -> dict:
    """Create an independent empty session. Does not replace an open browser scene."""
    return compact(await request("POST", "/api/sessions"))


@mcp.tool()
async def get_scene(session_id: str) -> dict:
    """Read portable scene, live object/joint poses, task progress, measured success and wrist camera pose."""
    return compact(await request("GET", f"/api/sessions/{session_id}"))


@mcp.tool()
async def scene_command(session_id: str, command: Command) -> dict:
    """Control the entire editor through typed commands. load takes a full scene; example loads spoon-to-cup; task takes source/target IDs; run/pause/stop/physics/step control execution. object_add takes object; object_update takes id/patch; object_remove takes id; robot takes joints or patch; camera takes camera/main|top|front and value/position,target,zoom,fov. Include revision on edits to reject stale changes. reset clears scene. run is asynchronous: poll get_scene until task.status succeeded/failed."""
    return compact(
        await request(
            "POST",
            f"/api/sessions/{session_id}/command",
            json=command.model_dump(exclude_none=True),
        )
    )


@mcp.tool()
async def import_mesh(
    filename: str, data_base64: str, longest_side_m: float = 0.1
) -> dict:
    """Convert local STL/OBJ/GLB file bytes (base64, max 10 MB decoded) to portable object. Add it with object_add. Convex hull collision, centered geometry, explicit size in meters. No server file access."""
    if len(data_base64) > 13_333_336:
        raise ValueError("File exceeds 10 MB")
    try:
        data = base64.b64decode(data_base64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64") from exc
    return await request(
        "POST",
        "/api/import",
        params={"filename": filename, "size": longest_side_m},
        content=data,
        headers={"Content-Type": "application/octet-stream"},
    )


@mcp.tool()
async def delete_session(session_id: str) -> dict:
    """Stop and close a session, disconnecting its viewers. Save its scene first if needed."""
    return await request("DELETE", f"/api/sessions/{session_id}")


@mcp.tool()
async def get_contract() -> dict:
    """JSON schemas for portable scenes and all editor commands, plus available primitive assets."""
    return {
        "scene": await request("GET", "/api/scene-schema"),
        "command": await request("GET", "/api/command-schema"),
        "assets": await request("GET", "/api/assets"),
    }


@mcp.tool()
async def camera_image(
    session_id: str, view: Literal["main", "top", "front", "wrist"] = "wrist"
) -> ImageContent:
    """Observe the simulated scene through a native MuJoCo camera as a 640×480 PNG. Wrist uses the actual robot-mounted camera. Free views use saved position/target. This is a physics renderer, so lighting differs from the editor."""
    async with httpx.AsyncClient(base_url=API, timeout=30, trust_env=False) as client:
        result = await client.get(
            f"/api/sessions/{session_id}/image", params={"view": view}
        )
        if result.is_error:
            raise ValueError(result.text)
        return ImageContent(
            type="image",
            data=base64.b64encode(result.content).decode(),
            mime_type="image/png",
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")
