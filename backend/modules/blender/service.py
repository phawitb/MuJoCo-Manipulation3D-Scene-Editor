"""Local silhouette solids. No Blender process, filesystem input or external service."""

import base64
import binascii
import io
import re
from typing import Protocol
from uuid import uuid4
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from scipy import ndimage
import trimesh
from ...schema import ImportedMesh, SceneObject
from .schemas import (
    MAX_IMAGE_BYTES,
    ReconstructionRequest,
    ReconstructionResult,
    ReconstructionMetadata,
)


class ReconstructionProvider(Protocol):
    def reconstruct(self, request: ReconstructionRequest) -> ReconstructionResult: ...


def _silhouette(request):
    try:
        data = base64.b64decode(request.image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(
            "Image must contain valid base64-encoded PNG or JPEG data"
        ) from exc
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be no larger than 6 MB")
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ("PNG", "JPEG"):
                raise ValueError("Choose a PNG or JPEG image")
            if max(source.size) > 4096 or source.width * source.height > 12_000_000:
                raise ValueError(
                    "Image dimensions must be at most 4096 per side and 12 million pixels"
                )
            if min(source.size) < 8:
                raise ValueError("Image dimensions must be at least 8 pixels per side")
            image = ImageOps.exif_transpose(source).convert("RGBA")
            pixels = list(image.size)
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Cannot read this image. Choose a valid PNG or JPEG.") from exc
    alpha = np.asarray(image.getchannel("A"))
    if request.foreground == "alpha":
        mask = alpha > request.threshold
    else:
        background = Image.new("RGBA", image.size, "white")
        gray = np.asarray(Image.alpha_composite(background, image).convert("L"))
        mask = (
            gray < request.threshold
            if request.foreground == "dark"
            else gray > request.threshold
        )
    if mask.sum() < 4 or mask.mean() > 0.98:
        raise ValueError(
            "No distinct foreground found. Adjust the threshold or foreground selection; leave background around the object."
        )
    labels, count = ndimage.label(mask)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    mask = labels == sizes.argmax()
    warnings = [
        "Approximate silhouette reconstruction: hidden surfaces, texture and real scale cannot be recovered from one photo.",
        "Gym uses convex mesh collision; visual holes and concavities are not physical openings.",
    ]
    if count > 1:
        warnings.append(
            "Only the largest connected foreground region was used. Detached parts were discarded."
        )
    ys, xs = np.nonzero(mask)
    mask = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    # Bound mesh complexity independently of source image resolution.
    thumb = Image.fromarray(mask.astype(np.uint8) * 255)
    thumb.thumbnail((64, 64), Image.Resampling.NEAREST)
    mask = np.asarray(thumb) > 127
    ys, xs = np.nonzero(mask)
    if len(xs) < 4:
        raise ValueError("Foreground is too thin at the bounded mesh resolution")
    mask = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    preview = io.BytesIO()
    Image.fromarray(mask.astype(np.uint8) * 255).save(preview, format="PNG")
    return mask, pixels, base64.b64encode(preview.getvalue()).decode(), warnings


def _extrude(mask, request):
    height, width = mask.shape
    vertices, faces, lookup = [], [], {}

    def vertex(x, row, side):
        key = (x, row, side)
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(
                [
                    (x / width - 0.5) * request.width_m,
                    (side - 0.5) * request.depth_m,
                    (0.5 - row / height) * request.height_m,
                ]
            )
        return lookup[key]

    def quad(points):
        a, b, c, d = [vertex(*point) for point in points]
        faces.extend([[a, b, c], [a, c, d]])

    for row, x in np.argwhere(mask):
        quad([(x, row, 0), (x + 1, row, 0), (x + 1, row + 1, 0), (x, row + 1, 0)])
        quad([(x, row + 1, 1), (x + 1, row + 1, 1), (x + 1, row, 1), (x, row, 1)])
        if row == 0 or not mask[row - 1, x]:
            quad([(x, row, 1), (x + 1, row, 1), (x + 1, row, 0), (x, row, 0)])
        if row == height - 1 or not mask[row + 1, x]:
            quad(
                [
                    (x, row + 1, 0),
                    (x + 1, row + 1, 0),
                    (x + 1, row + 1, 1),
                    (x, row + 1, 1),
                ]
            )
        if x == 0 or not mask[row, x - 1]:
            quad([(x, row, 0), (x, row + 1, 0), (x, row + 1, 1), (x, row, 1)])
        if x == width - 1 or not mask[row, x + 1]:
            quad(
                [
                    (x + 1, row, 1),
                    (x + 1, row + 1, 1),
                    (x + 1, row + 1, 0),
                    (x + 1, row, 0),
                ]
            )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=True)


def _revolve(mask, request):
    height, width = mask.shape
    if not mask.any(axis=1).all():
        raise ValueError(
            "Revolve needs a continuous front-on silhouette with no detached rows"
        )
    # Symmetrize the outside profile about the image's vertical bounding-box axis.
    radii = []
    for row in mask:
        xs = np.flatnonzero(row)
        radii.append(max(width / 2 - xs[0], xs[-1] + 1 - width / 2))
    radii = np.asarray(radii, dtype=float)
    radii *= (request.width_m / 2) / radii.max()
    # Row-centre samples plus full-height end rings keep entered dimensions exact.
    z = np.r_[
        -request.height_m / 2,
        ((np.arange(height) + 0.5) / height - 0.5) * request.height_m,
        request.height_m / 2,
    ]
    r = np.r_[radii[-1], radii[::-1], radii[0]]
    angles = np.arange(48) * (2 * np.pi / 48)
    vertices = [
        [radius * np.cos(a), radius * np.sin(a), level]
        for radius, level in zip(r, z)
        for a in angles
    ]
    faces = []
    for ring in range(len(z) - 1):
        for col in range(48):
            a, b = ring * 48 + col, ring * 48 + (col + 1) % 48
            faces.extend([[a, b, b + 48], [a, b + 48, a + 48]])
    vertices.extend([[0, 0, z[0]], [0, 0, z[-1]]])
    for col in range(48):
        nxt = (col + 1) % 48
        faces.extend(
            [
                [len(vertices) - 2, nxt, col],
                [len(vertices) - 1, (len(z) - 1) * 48 + col, (len(z) - 1) * 48 + nxt],
            ]
        )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=True)


class LocalSilhouetteProvider:
    def reconstruct(self, request):
        mask, pixels, preview, warnings = _silhouette(request)
        mesh = (
            _extrude(mask, request)
            if request.mode == "extrude"
            else _revolve(mask, request)
        )
        mesh.fix_normals()
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(
                "Silhouette has touching edges or disconnected details that cannot make a closed solid. Use a cleaner silhouette or adjust the threshold."
            )
        if len(mesh.vertices) > 20000 or len(mesh.faces) > 40000:
            raise ValueError("Silhouette is too complex; simplify the image")
        if request.mode == "revolve":
            warnings.append(
                "Revolve makes a solid symmetric outer shape. Cavities, handles and off-axis details are not reconstructed; depth is the entered diameter."
            )
        name = request.name.strip() or "Image object"
        filename = (
            re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-")[:60] or "image-object"
        ) + ".glb"
        mesh.visual.face_colors = [143, 185, 177, 255]
        obj = SceneObject(
            id="image_" + uuid4().hex[:12],
            name=name,
            asset="mesh",
            mesh=ImportedMesh(
                vertices=mesh.vertices.reshape(-1).tolist(),
                faces=mesh.faces.reshape(-1).tolist(),
                filename=filename,
            ),
            color="#8fb9b1",
            mass=0.05,
            position=[0.06, 0, 0.752 + request.height_m / 2],
        )
        # glTF is Y-up; keep the portable Gym mesh Z-up and rotate only export.
        exported = mesh.copy()
        exported.apply_transform(
            np.array(
                [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float
            )
        )
        return ReconstructionResult(
            object=obj,
            glb_base64=base64.b64encode(exported.export(file_type="glb")).decode(),
            filename=filename,
            metadata=ReconstructionMetadata(
                mode=request.mode,
                dimensions_m=mesh.extents.tolist(),
                vertices=len(mesh.vertices),
                triangles=len(mesh.faces),
                watertight=True,
                volume_m3=float(mesh.volume),
                source_pixels=pixels,
                mask_png_base64=preview,
                warnings=warnings,
            ),
        )


provider: ReconstructionProvider = LocalSilhouetteProvider()


def reconstruct(request: ReconstructionRequest) -> ReconstructionResult:
    return provider.reconstruct(request)
