"""Typed MCP facade; HTTP service remains the sole hardware owner."""

import base64
import httpx
from mcp.types import ImageContent
from .schemas import (
    Connect,
    Owner,
    Calibration,
    Jog,
    Sync,
    Scan,
    Assignments,
    RobotPort,
)


def register(mcp, request, api_url):
    @mcp.tool()
    async def connection_status() -> dict:
        """Read physical SO101 identity, measured telemetry, calibration, owner and faults. No motion."""
        return await request("GET", "/api/connection/status")

    @mcp.tool()
    async def connection_ports() -> dict:
        """Discover local serial ports without opening or changing them."""
        return await request("GET", "/api/connection/ports")

    @mcp.tool()
    async def connection_settings() -> dict:
        """Read locally persisted joint mapping and back/front/wrist camera indices."""
        return await request("GET", "/api/connection/settings")

    @mcp.tool()
    async def configure_robot_port(port: RobotPort) -> dict:
        """Persist the local serial port used by Gym and verification. No motion."""
        return await request("PUT", "/api/connection/port", json=port.model_dump())

    @mcp.tool()
    async def verify_connections() -> dict:
        """Read all six motors without motion and capture only assigned camera indices. Does not create a Gym session or claim hardware ownership."""
        return await request("POST", "/api/connection/verify")

    @mcp.tool()
    async def connect_robot(connection: Connect) -> dict:
        """Read-only connect and verify six STS3215 motors. Bind ownership to an existing Gym session. Never enables torque."""
        return await request(
            "POST", "/api/connection/connect", json=connection.model_dump()
        )

    @mcp.tool()
    async def calibrate_robot(calibration: Calibration) -> dict:
        """Save explicitly verified encoder-to-radian mapping for connected device identity. Never guess zero from the current pose. Does not write motor EEPROM."""
        return await request(
            "PUT", "/api/connection/calibration", json=calibration.model_dump()
        )

    @mcp.tool()
    async def align_gym_to_robot(owner: Owner) -> dict:
        """Match the selected Gym to fresh measured arm angles once. No motor writes. Stop motion/sync first; requires calibration and a collision-free measured pose."""
        return await request("POST", "/api/connection/align", json=owner.model_dump())

    @mcp.tool()
    async def enable_robot(owner: Owner) -> dict:
        """Enable physical movement at measured current pose, requiring verified calibration and safe pose. Renew heartbeat every second. This moves real hardware on later jog/sync."""
        return await request("POST", "/api/connection/enable", json=owner.model_dump())

    @mcp.tool()
    async def robot_heartbeat(owner: Owner) -> dict:
        """Renew active physical controller lease (expires after three seconds). Call at least once per second while driving."""
        return await request(
            "POST", "/api/connection/heartbeat", json=owner.model_dump()
        )

    @mcp.tool()
    async def jog_robot(jog: Jog) -> dict:
        """Bounded physical joint movement, radians, maximum ±0.05 per request. Requires enabled calibrated owner; joint/path/tracking guards apply."""
        return await request("POST", "/api/connection/jog", json=jog.model_dump())

    @mcp.tool()
    async def sync_robot(sync: Sync) -> dict:
        """Explicit realtime direction real_to_gym or gym_to_real; off stops sync. Physical output requires matched safe starting pose. Poll measured feedback; renew heartbeat."""
        return await request("POST", "/api/connection/sync", json=sync.model_dump())

    @mcp.tool()
    async def stop_robot(owner: Owner) -> dict:
        """Stop streaming and hold measured pose when feedback is available. Keeps torque; not an emergency power cut."""
        return await request("POST", "/api/connection/stop", json=owner.model_dump())

    @mcp.tool()
    async def disconnect_robot(owner: Owner) -> dict:
        """Stop synchronization and close serial connection without silently releasing gravity-loaded joints."""
        return await request(
            "POST", "/api/connection/disconnect", json=owner.model_dump()
        )

    @mcp.tool()
    async def scan_physical_cameras(scan: Scan) -> dict:
        """Check indices 0 through max_index for local image capture, bounded time per camera. Camera permissions may be needed."""
        return await request(
            "POST", "/api/connection/cameras/scan", json=scan.model_dump()
        )

    @mcp.tool()
    async def assign_physical_cameras(assignments: Assignments) -> dict:
        """Persist distinct local camera indices for back/front/wrist. Null clears a role."""
        return await request(
            "PUT", "/api/connection/cameras/assignments", json=assignments.model_dump()
        )

    @mcp.tool()
    async def physical_camera_image(index: int) -> ImageContent:
        """Read an actual local camera frame (JPEG). Indices 0–7; use scan_physical_cameras first."""
        if not 0 <= index <= 7:
            raise ValueError("Camera index must be 0–7")
        async with httpx.AsyncClient(
            base_url=api_url, timeout=10, trust_env=False
        ) as client:
            result = await client.get(f"/api/connection/cameras/{index}/frame")
            if result.is_error:
                raise ValueError(result.text)
            return ImageContent(
                type="image",
                data=base64.b64encode(result.content).decode(),
                mime_type="image/jpeg",
            )
