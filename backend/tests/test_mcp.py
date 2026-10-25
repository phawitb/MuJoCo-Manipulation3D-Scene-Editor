"""Actual SDK handshake and tool dispatch over stdio against a local service."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_mcp_handshake_tools_and_shared_scene():
    root = Path(__file__).resolve().parents[2]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                if httpx.get(url + "/api/health").status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(0.05)

        async def exercise():
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "backend.mcp_server"],
                cwd=str(root),
                env={**os.environ, "SO101_API_URL": url},
            )
            async with (
                stdio_client(params) as (read, write),
                ClientSession(read, write) as client,
            ):
                await client.initialize()
                listing = await client.list_tools()
                assert {
                    "list_sessions",
                    "create_session",
                    "get_scene",
                    "scene_command",
                    "import_mesh",
                    "connection_status",
                    "connect_robot",
                    "robot_joint_target",
                    "robot_home",
                    "match_robot_to_gym",
                    "robot_torque",
                    "recover_robot_limits",
                    "robot_tool_target",
                    "configure_robot_port",
                    "verify_connections",
                    "stop_robot",
                    "sync_robot",
                    "calibrate_robot",
                    "robot_heartbeat",
                    "scan_physical_cameras",
                    "assign_physical_cameras",
                    "physical_camera_image",
                    "create_object_from_image",
                } <= {t.name for t in listing.tools}
                status = await client.call_tool("connection_status", {})
                assert not status.is_error
                assert json.loads(status.content[0].text)["connected"] is False
                result = await client.call_tool("create_session", {})
                assert not result.is_error
                payload = json.loads(result.content[0].text)
                sid = payload["sessionId"]
                result = await client.call_tool(
                    "scene_command", {"session_id": sid, "command": {"type": "example"}}
                )
                assert not result.is_error
                state = httpx.get(url + "/api/sessions/" + sid).json()
                assert state["scene"]["task"] == {"source": "spoon", "target": "cup"}
                examples = await client.call_tool("list_examples", {})
                assert not examples.is_error
                result = await client.call_tool(
                    "scene_command", {"session_id": sid, "command": {"type": "plan"}}
                )
                assert not result.is_error
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    result = await client.call_tool("get_scene", {"session_id": sid})
                    if (
                        json.loads(result.content[0].text)["plan"]["status"]
                        != "calculating"
                    ):
                        break
                    await asyncio.sleep(0.03)
                assert json.loads(result.content[0].text)["plan"]["verified"]
                result = await client.call_tool(
                    "scene_command", {"session_id": sid, "command": {"type": "run"}}
                )
                assert not result.is_error
                result = await client.call_tool(
                    "scene_command", {"session_id": sid, "command": {"type": "pause"}}
                )
                assert not result.is_error
                image = await client.call_tool(
                    "camera_image", {"session_id": sid, "view": "wrist"}
                )
                assert not image.is_error
                assert image.content[0].type == "image"
                invalid = await client.call_tool(
                    "scene_command",
                    {
                        "session_id": sid,
                        "command": {"type": "task", "source": "missing"},
                    },
                )
                assert invalid.is_error

        asyncio.run(exercise())
    finally:
        server.terminate()
        server.wait(timeout=10)
