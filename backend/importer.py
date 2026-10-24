"""Bounded, self-contained mesh conversion; no arbitrary filesystem paths."""

import io
import math
from pathlib import PurePath
from uuid import uuid4
import numpy as np
import trimesh
from .schema import ImportedMesh, SceneObject

MAX_UPLOAD = 10_000_000
MAX_SCENE = 8_000_000


def import_object(data: bytes, filename: str, size: float = 0.10) -> SceneObject:
    ext = PurePath(filename).suffix.lower().lstrip(".")
    if ext not in ("stl", "obj", "glb"):
        raise ValueError("Choose an STL, OBJ or self-contained GLB file")
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError("Object file must be between 1 byte and 10 MB")
    if not math.isfinite(size) or not 0.005 <= size <= 1.0:
        raise ValueError("Longest side must be between 0.005 and 1 meter")
    try:
        mesh = trimesh.load(
            io.BytesIO(data),
            file_type=ext,
            force="mesh",
            process=True,
            resolver={},
            skip_materials=True,
        )
        if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
            raise ValueError("No triangular geometry found")
        if len(mesh.vertices) > 20000 or len(mesh.faces) > 40000:
            raise ValueError(
                "Mesh is too detailed: simplify to 20,000 vertices / 40,000 triangles"
            )
        if not np.isfinite(mesh.vertices).all():
            raise ValueError("Mesh contains non-finite vertices")
        extent = mesh.extents
        if (
            extent.max() <= 0
            or extent.min() / extent.max() < 1e-5
            or mesh.convex_hull.volume <= 1e-12
        ):
            raise ValueError("Object needs solid volume / thickness for collision")
        mesh.vertices -= mesh.bounds.mean(axis=0)
        mesh.vertices *= size / extent.max()
        name = PurePath(filename.replace("\\", "/")).name[:120]
        portable = ImportedMesh(
            vertices=mesh.vertices.reshape(-1).tolist(),
            faces=mesh.faces.reshape(-1).tolist(),
            filename=name,
        )
        return SceneObject(
            id="mesh_" + uuid4().hex[:8],
            name=PurePath(name).stem[:80] or "Imported object",
            asset="mesh",
            mesh=portable,
            mass=0.05,
            color="#8fb9b1",
            position=[0.06, 0, 0.752 + float(mesh.extents[2]) / 2],
        )
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            "Cannot read this object file. Export a valid STL, OBJ or self-contained GLB."
        ) from exc
