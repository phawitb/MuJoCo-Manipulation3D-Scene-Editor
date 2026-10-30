"""Portable, validated rigid-object data. No XML or filesystem dependencies."""

from typing import Annotated, Literal
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

V3 = Annotated[list[float], Field(min_length=3, max_length=3)]
Q4 = Annotated[list[float], Field(min_length=4, max_length=4)]


class PackageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PackageMesh(PackageModel):
    vertices: list[float] = Field(min_length=12, max_length=180000)
    faces: list[int] = Field(min_length=12, max_length=360000)

    @model_validator(mode="after")
    def valid_mesh(self):
        if (
            len(self.vertices) % 3
            or len(self.faces) % 3
            or max(map(abs, self.vertices)) > 2
        ):
            raise ValueError("Invalid package mesh vertices")
        if min(self.faces) < 0 or max(self.faces) >= len(self.vertices) // 3:
            raise ValueError("Invalid package mesh faces")
        return self


class PackageGeom(PackageModel):
    kind: Literal["box", "sphere", "ellipsoid", "capsule", "cylinder", "mesh"]
    position: V3
    quaternion: Q4
    size: V3
    mesh: int | None = None
    rgba: Q4
    group: int = Field(ge=0, le=5)
    contype: int = Field(ge=0, le=2147483647)
    conaffinity: int = Field(ge=0, le=2147483647)
    condim: Literal[1, 3, 4, 6]
    friction: V3
    solref: Annotated[list[float], Field(min_length=2, max_length=2)]
    solimp: Annotated[list[float], Field(min_length=5, max_length=5)]
    priority: int = Field(ge=0, le=100)
    solmix: float = Field(ge=0, le=1)
    margin: float = Field(ge=0, le=0.1)
    gap: float = Field(ge=0, le=0.1)
    material: dict[
        Literal["specular", "shininess", "reflectance", "emission"], float
    ] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_geom(self):
        if max(map(abs, self.position)) > 2 or max(self.size) > 2 or min(self.size) < 0:
            raise ValueError("Package geometry exceeds 2 m bounds")
        if abs(np.linalg.norm(self.quaternion) - 1) > 1e-5:
            raise ValueError("Package rotation must be normalized")
        if (
            min(self.rgba) < 0
            or max(self.rgba) > 1
            or min(self.friction) < 0
            or max(self.friction) > 5
        ):
            raise ValueError("Invalid package color or friction")
        if (self.kind == "mesh") != (self.mesh is not None):
            raise ValueError("Package mesh reference required only for mesh geoms")
        if any(not 0 <= v <= 1 for v in self.material.values()):
            raise ValueError("Invalid package material")
        return self


class RigidPackage(PackageModel):
    version: Literal[1] = 1
    source: str = Field(max_length=200)
    dimensions: V3
    mass: float = Field(ge=0.001, le=10)
    com: V3
    inertia: Annotated[list[float], Field(min_length=6, max_length=6)]
    geoms: list[PackageGeom] = Field(min_length=1, max_length=256)
    meshes: list[PackageMesh] = Field(default_factory=list, max_length=128)
    sites: dict[str, V3] = Field(default_factory=dict, max_length=64)
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_package(self):
        import json

        if (
            min(self.dimensions) <= 0
            or max(self.dimensions) > 2
            or max(map(abs, self.com)) > 2
        ):
            raise ValueError("Invalid package dimensions or center of mass")
        xx, yy, zz, xy, xz, yz = self.inertia
        eig = np.linalg.eigvalsh([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])
        if eig[0] <= 0 or eig[2] > eig[0] + eig[1] + 1e-12:
            raise ValueError("Invalid physical inertia tensor")
        if (
            sum(len(m.vertices) for m in self.meshes) > 180000
            or sum(len(m.faces) for m in self.meshes) > 360000
        ):
            raise ValueError("Package exceeds 60k vertices / 120k triangles")
        for g in self.geoms:
            if g.mesh is not None and not 0 <= g.mesh < len(self.meshes):
                raise ValueError("Missing package mesh reference")
        if len(json.dumps(self.provenance).encode()) > 100000:
            raise ValueError("Package metadata exceeds 100 KB")
        if any(len(k) > 100 or max(map(abs, v)) > 2 for k, v in self.sites.items()):
            raise ValueError("Invalid package site")
        return self
