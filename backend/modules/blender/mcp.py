"""Local reconstruction exposed through the same validated HTTP contract."""

from .schemas import ReconstructionRequest


def register(mcp, request):
    @mcp.tool()
    async def create_object_from_image(reconstruction: ReconstructionRequest) -> dict:
        """Create approximate local silhouette extrusion or solid revolve from image bytes. Enter actual dimensions; hidden surfaces cannot be recovered. Returns portable object, GLB and mask preview. Add object to explicit scene using scene_command object_add. Convex Gym collision does not preserve cavities."""
        return await request(
            "POST", "/api/blender/create", json=reconstruction.model_dump()
        )
