"""Portable request/response contracts for replaceable local reconstruction providers."""

from typing import Literal
from pydantic import Field
from ...schema import StrictModel, SceneObject

MAX_IMAGE_BYTES = 6_000_000
MAX_REQUEST_BYTES = 8_100_000


class ReconstructionRequest(StrictModel):
    image_base64: str = Field(min_length=4, max_length=8_000_000)
    filename: str = Field(default="image.png", min_length=1, max_length=120)
    name: str = Field(default="Image object", min_length=1, max_length=80)
    mode: Literal["extrude", "revolve"] = "extrude"
    foreground: Literal["dark", "light", "alpha"] = "dark"
    threshold: int = Field(default=128, ge=0, le=255, strict=True)
    width_m: float = Field(default=0.10, ge=0.005, le=1)
    height_m: float = Field(default=0.10, ge=0.005, le=1)
    depth_m: float = Field(default=0.03, ge=0.005, le=1)


class ReconstructionMetadata(StrictModel):
    provider: Literal["local-silhouette"] = "local-silhouette"
    mode: Literal["extrude", "revolve"]
    dimensions_m: list[float] = Field(min_length=3, max_length=3)
    vertices: int
    triangles: int
    watertight: bool
    volume_m3: float
    source_pixels: list[int] = Field(min_length=2, max_length=2)
    mask_png_base64: str
    warnings: list[str]


class ReconstructionResult(StrictModel):
    object: SceneObject
    glb_base64: str
    filename: str
    metadata: ReconstructionMetadata
