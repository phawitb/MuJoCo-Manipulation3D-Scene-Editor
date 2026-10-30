"""Bounded package-local MJCF import; compile only an isolated rigid object."""

import copy
import io
import json
from pathlib import PurePosixPath
import stat
import zipfile
import xml.etree.ElementTree as ET
from uuid import uuid4
import mujoco
import numpy as np
from .package_schema import RigidPackage, PackageGeom, PackageMesh

MAX_PACKAGE_BYTES = 10_000_000
MAX_EXPANDED_BYTES = 20_000_000
MAX_FILES = 256
KINDS = {
    int(getattr(mujoco.mjtGeom, "mjGEOM_" + s.upper())): s
    for s in ("sphere", "capsule", "ellipsoid", "cylinder", "box", "mesh")
}


def safe_path(path):
    if (
        not path
        or "\\" in path
        or ":" in path
        or path.startswith("/")
        or ".." in path.split("/")
        or "\x00" in path
    ):
        raise ValueError(f"Unsafe package path: {path[:160]}")
    return str(PurePosixPath(path))


def import_package_zip(data):
    if not data or len(data) > MAX_PACKAGE_BYTES:
        raise ValueError("ZIP must be at most 10 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > MAX_FILES
                or sum(i.file_size for i in entries) > MAX_EXPANDED_BYTES
            ):
                raise ValueError("Package exceeds 256 files or 20 MB expanded size")
            files = {}
            for item in entries:
                path = safe_path(item.filename)
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError("Package paths cannot be symbolic links")
                if item.is_dir():
                    continue
                if path in files:
                    raise ValueError("Duplicate package path")
                files[path] = archive.read(item)
            return import_package(files)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError("Cannot read this ZIP package") from exc


def _read_xml(files, path, stack=(), budget=None):
    budget = [0] if budget is None else budget
    if path in stack or len(stack) >= 12:
        raise ValueError("Recursive or excessive XML includes")
    data = files.get(path)
    if data is None:
        raise ValueError(f"Missing package file: {path}")
    budget[0] += len(data)
    if budget[0] > 4_000_000:
        raise ValueError("Expanded XML includes exceed 4 MB")
    try:
        data = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Package XML must use UTF-8") from exc
    if len(data) > 1_000_000:
        raise ValueError("XML exceeds 1 MB")
    if "<!DOCTYPE" in data.upper() or "<!ENTITY" in data.upper():
        raise ValueError("XML DOCTYPE/entities are unsupported")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML in {path}: {exc}") from exc
    for parent in list(root.iter()):
        for node in list(parent):
            if node.tag == "include":
                ref = safe_path(node.get("file", ""))
                target = safe_path(str(PurePosixPath(path).parent / ref))
                included = _read_xml(files, target, (*stack, path), budget)
                index = list(parent).index(node)
                parent.remove(node)
                for child in reversed(list(included)):
                    parent.insert(index, child)
    return root


# Only attributes represented by the portable format (or resolved by compilation)
# may affect the object. Reject extra physics rather than silently dropping it.
POSE = {"pos", "quat", "euler", "axisangle", "xyaxes", "zaxis"}
SUPPORTED_ATTRIBUTES = {
    "body": POSE | {"name", "childclass"},
    "frame": POSE | {"name", "childclass"},
    "freejoint": {"name", "group"},
    "joint": {"name", "type", "group"},
    "geom": POSE
    | {
        "name",
        "class",
        "type",
        "size",
        "fromto",
        "mesh",
        "rgba",
        "material",
        "group",
        "contype",
        "conaffinity",
        "condim",
        "friction",
        "solref",
        "solimp",
        "priority",
        "solmix",
        "margin",
        "gap",
        "mass",
        "density",
    },
    "inertial": POSE | {"mass", "diaginertia", "fullinertia"},
    "material": {
        "name",
        "class",
        "rgba",
        "specular",
        "shininess",
        "reflectance",
        "emission",
    },
    "mesh": {
        "name",
        "class",
        "file",
        "vertex",
        "face",
        "scale",
        "refpos",
        "refquat",
        "normal",
        "texcoord",
        "inertia",
    },
    "default": {"class"},
    "site": POSE
    | {"name", "class", "type", "size", "fromto", "rgba", "material", "group"},
}


def _validate_supported(node):
    allowed = SUPPORTED_ATTRIBUTES.get(node.tag)
    if allowed is not None and set(node.attrib) - allowed:
        extra = ", ".join(sorted(set(node.attrib) - allowed))
        raise ValueError(f"Unsupported {node.tag} settings: {extra}")
    if node.tag == "geom" and int(node.get("group", "0")) > 3:
        raise ValueError(
            "Unsupported geom group: use 0–2 for visuals and 3 for hidden collision"
        )


def _body_contexts(root, inherited=None, top_only=False):
    """Retain effective childclass when removing demonstration frames/parents."""
    effective = root.get("childclass", inherited)
    if root.tag == "body":
        yield root, inherited
        if top_only:
            return
    for child in root:
        yield from _body_contexts(child, effective, top_only)


def _object_model(files):
    entry = "scene.xml" if "scene.xml" in files else "object.xml"
    if entry not in files:
        raise ValueError("Package needs object.xml or scene.xml")
    source = _read_xml(files, entry)
    allowed = {
        "mujoco",
        "mujocoinclude",
        "compiler",
        "option",
        "visual",
        "statistic",
        "asset",
        "mesh",
        "material",
        "default",
        "worldbody",
        "body",
        "frame",
        "geom",
        "joint",
        "freejoint",
        "inertial",
        "site",
        "light",
    }
    # Unsupported physics is rejected even if it occurs outside the selected body.
    for node in source.iter():
        if node.tag not in allowed:
            raise ValueError(f"Unsupported package element: {node.tag}")
        if node.tag == "joint" and node.get("type", "hinge") != "free":
            raise ValueError(
                "Articulated/internal joints are unsupported; import one rigid object"
            )
        if node.tag == "mesh" and any(
            k in node.attrib for k in ("plugin", "content_type")
        ):
            raise ValueError("Unsupported mesh extension")
    if "object.xml" in files:
        object_root = _read_xml(files, "object.xml")
        # Validate object.xml even when scene.xml does not reference it.
        for n in object_root.iter():
            if n.tag not in allowed:
                raise ValueError(f"Unsupported package element: {n.tag}")
        contexts = list(_body_contexts(object_root, top_only=True))
        bodies = [b for b, _ in contexts]
    else:
        bodies = [
            b
            for b in source.iter("body")
            if b.find("freejoint") is not None
            or b.find("joint[@type='free']") is not None
        ]
    if len(bodies) != 1:
        raise ValueError("Package must contain exactly one rigid object body")
    selected = bodies[0]
    inherited = None
    if "object.xml" in files:
        inherited = contexts[0][1]
        if entry == "scene.xml":
            matching = [
                (b, default)
                for b, default in _body_contexts(source)
                if (
                    b.get("name") == selected.get("name")
                    if selected.get("name")
                    else ET.tostring(b) == ET.tostring(selected)
                )
            ]
            if len(matching) == 1:
                selected, inherited = matching[0]
            elif len(matching) > 1:
                raise ValueError("Ambiguous object bodies in scene.xml")
    else:
        inherited = next(
            default for b, default in _body_contexts(source) if b is selected
        )
    body = copy.deepcopy(selected)
    if inherited and not body.get("childclass"):
        body.set("childclass", inherited)
    joints = list(body.iter("joint")) + list(body.iter("freejoint"))
    if (
        len(joints) > 1
        or any(j.tag == "joint" and j.get("type", "hinge") != "free" for j in joints)
        or any(j not in list(body) for j in joints)
    ):
        raise ValueError("Articulated/internal joints are unsupported")
    for node in body.iter():
        _validate_supported(node)
    for j in joints:
        body.remove(j)
    # Imported root pose is demonstration placement, not intrinsic geometry.
    for key in ("pos", "quat", "euler", "axisangle", "xyaxes", "zaxis"):
        body.attrib.pop(key, None)
    ET.SubElement(body, "freejoint")
    root = ET.Element("mujoco")
    compiler = source.find("compiler")
    attrs = {"angle": "degree", "inertiafromgeom": "auto", "fusestatic": "false"}
    if compiler is not None:
        for k in ("angle", "eulerseq"):
            if k in compiler.attrib:
                attrs[k] = compiler.get(k)
        unsupported = set(compiler.attrib) - {
            "angle",
            "eulerseq",
            "autolimits",
            "meshdir",
            "texturedir",
            "assetdir",
            "inertiafromgeom",
            "fusestatic",
        }
        if unsupported:
            raise ValueError(
                f"Unsupported compiler settings: {', '.join(sorted(unsupported))}"
            )
        if compiler.get("inertiafromgeom", "auto") != "auto":
            raise ValueError("Unsupported compiler inertiafromgeom override")
    ET.SubElement(root, "compiler", **attrs)
    assets = source.findall("asset")
    if not assets and "assets.xml" in files:
        assets = _read_xml(files, "assets.xml").findall("asset")
    for default in source.findall("default"):
        root.append(copy.deepcopy(default))
    asset = ET.SubElement(root, "asset")
    binary = {}
    meshdir = (
        compiler.get("meshdir", compiler.get("assetdir", ""))
        if compiler is not None
        else ""
    )
    for section in assets:
        for child in section:
            if child.tag not in ("mesh", "material"):
                raise ValueError(f"Unsupported package asset: {child.tag}")
            item = copy.deepcopy(child)
            if item.tag == "material" and any(
                k.startswith("texture") for k in item.attrib
            ):
                raise ValueError("Image-textured materials are not supported yet")
            if item.tag == "mesh" and "file" in item.attrib:
                ref = safe_path(item.get("file"))
                path = safe_path(str(PurePosixPath(meshdir) / ref)) if meshdir else ref
                if path not in files:
                    raise ValueError(f"Missing mesh asset: {path}")
                if PurePosixPath(path).suffix.lower() not in (".obj", ".stl"):
                    raise ValueError("Package meshes must be OBJ or STL")
                item.set("file", path)
                binary[path] = files[path]
            asset.append(item)
    ET.SubElement(root, "worldbody").append(body)
    # The isolated document is the only input allowed to reach MuJoCo.
    for n in root.iter():
        _validate_supported(n)
        if n.tag not in allowed:
            raise ValueError(f"Unsupported package element: {n.tag}")
        for k in n.attrib:
            if k in ("file", "filename") and not (n.tag == "mesh" and k == "file"):
                raise ValueError(f"Unsupported external reference on {n.tag}")
            if k == "file" and n.get(k) not in binary:
                raise ValueError("Missing package-local file data")
    if sum(1 for _ in root.iter()) > 1500:
        raise ValueError("Package XML is too complex")
    try:
        model = mujoco.MjModel.from_xml_string(
            ET.tostring(root, encoding="unicode"), assets=binary
        )
    except Exception as exc:
        raise ValueError(f"Cannot compile package object: {str(exc)[:500]}") from exc
    if (
        model.ngeom > 256
        or model.nmesh > 128
        or model.nmeshvert > 60000
        or model.nmeshface > 120000
    ):
        raise ValueError(
            "Package exceeds geometry budget (256 parts, 60k vertices / 120k triangles)"
        )
    return model, body.get("name", "Imported MuJoCo object"), entry


def import_package(files):
    from .schema import SceneObject, MAX_SCENE_BYTES

    if (
        not files
        or len(files) > MAX_FILES
        or sum(len(b) for b in files.values()) > MAX_EXPANDED_BYTES
    ):
        raise ValueError("Package exceeds 256 files or 20 MB expanded size")
    normalized = {}
    for name, data in files.items():
        path = safe_path(name)
        if path in normalized:
            raise ValueError("Duplicate package path")
        normalized[path] = data
    files = normalized
    # A browser folder or ZIP often wraps all files in one containing directory.
    while (
        files
        and all("/" in n for n in files)
        and len({n.split("/")[0] for n in files}) == 1
    ):
        files = {n.split("/", 1)[1]: b for n, b in files.items()}
    model, name, entry = _object_model(files)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    meshes = [
        PackageMesh(
            vertices=model.mesh_vert[a : a + n].reshape(-1).tolist(),
            faces=model.mesh_face[f : f + c].reshape(-1).tolist(),
        )
        for a, n, f, c in zip(
            model.mesh_vertadr,
            model.mesh_vertnum,
            model.mesh_faceadr,
            model.mesh_facenum,
        )
    ]
    parts = []
    bounds = []
    for i in range(model.ngeom):
        kind = KINDS.get(int(model.geom_type[i]))
        if kind is None:
            raise ValueError(
                "Unsupported object geometry (planes/heightfields are not objects)"
            )
        r = data.geom_xmat[i].reshape(3, 3)
        pos = data.geom_xpos[i].copy()
        q = np.empty(4)
        mujoco.mju_mat2Quat(q, r.reshape(-1))
        size = model.geom_size[i].copy()
        mid = int(model.geom_dataid[i]) if kind == "mesh" else None
        if mid is not None:
            points = np.array(meshes[mid].vertices).reshape(-1, 3) @ r.T + pos
            bounds.extend([points.min(axis=0), points.max(axis=0)])
        else:
            if kind == "sphere":
                half = np.repeat(size[0], 3)
            elif kind == "ellipsoid":
                half = np.sqrt((r * r) @ (size * size))
            elif kind == "capsule":
                half = np.abs(r[:, 2]) * size[1] + size[0]
            elif kind == "cylinder":
                half = np.abs(r[:, 2]) * size[1] + size[0] * np.sqrt(
                    np.maximum(0, 1 - r[:, 2] ** 2)
                )
            else:
                half = np.abs(r) @ size
            bounds.extend([pos - half, pos + half])
        mat = int(model.geom_matid[i])
        rgba = model.geom_rgba[i].copy()
        material = {}
        if mat >= 0:
            if np.allclose(rgba, [0.5, 0.5, 0.5, 1]):
                rgba = model.mat_rgba[mat].copy()
            material = {
                k: float(getattr(model, "mat_" + k)[mat])
                for k in ("specular", "shininess", "reflectance", "emission")
            }
        parts.append(
            PackageGeom(
                kind=kind,
                position=pos.tolist(),
                quaternion=q.tolist(),
                size=size.tolist(),
                mesh=mid,
                rgba=rgba.tolist(),
                group=int(model.geom_group[i]),
                contype=int(model.geom_contype[i]),
                conaffinity=int(model.geom_conaffinity[i]),
                condim=int(model.geom_condim[i]),
                friction=model.geom_friction[i].tolist(),
                solref=model.geom_solref[i].tolist(),
                solimp=model.geom_solimp[i].tolist(),
                priority=int(model.geom_priority[i]),
                solmix=float(model.geom_solmix[i]),
                margin=float(model.geom_margin[i]),
                gap=float(model.geom_gap[i]),
                material=material,
            )
        )
    if not parts:
        raise ValueError("Package object contains no geometry")
    low = np.min(bounds, axis=0)
    high = np.max(bounds, axis=0)
    center = (low + high) / 2
    total = float(model.body_mass[1:].sum())
    if not 0.001 <= total <= 10:
        raise ValueError("Package mass must be between 0.001 and 10 kg")
    com = (data.xipos[1:] * model.body_mass[1:, None]).sum(axis=0) / total
    tensor = np.zeros((3, 3))
    for b in range(1, model.nbody):
        r = data.ximat[b].reshape(3, 3)
        delta = data.xipos[b] - com
        tensor += r @ np.diag(model.body_inertia[b]) @ r.T + model.body_mass[b] * (
            np.dot(delta, delta) * np.eye(3) - np.outer(delta, delta)
        )
    for p in parts:
        p.position = (np.array(p.position) - center).tolist()
    provenance = {}
    for fn in (
        "physics.json",
        "parameters.json",
        "calibration.json",
        "validation.json",
    ):
        if fn in files:
            if len(files[fn]) > 100000:
                raise ValueError("Package metadata exceeds 100 KB")
            try:
                provenance[fn] = json.loads(files[fn])
            except (ValueError, UnicodeError) as exc:
                raise ValueError(f"Invalid metadata: {fn}") from exc
    package = RigidPackage(
        source=entry,
        dimensions=(high - low).tolist(),
        mass=total,
        com=(com - center).tolist(),
        inertia=[
            tensor[0, 0],
            tensor[1, 1],
            tensor[2, 2],
            tensor[0, 1],
            tensor[0, 2],
            tensor[1, 2],
        ],
        geoms=parts,
        meshes=meshes,
        sites={
            model.site(i).name or f"site_{i}": (data.site_xpos[i] - center).tolist()
            for i in range(model.nsite)
        },
        provenance=provenance,
    )
    contact = next((g for g in parts if g.contype or g.conaffinity), parts[0])
    color = next((g.rgba for g in parts if g.group not in (3, 4)), parts[0].rgba)
    obj = SceneObject(
        id="mujoco_" + uuid4().hex[:8],
        name=name[:80],
        asset="mujoco",
        package=package,
        mass=total,
        friction=contact.friction,
        color="#" + "".join(f"{round(float(c) * 255):02x}" for c in color[:3]),
        position=[0.06, 0, 0.752 + float(package.dimensions[2]) / 2],
    )
    if len(obj.model_dump_json().encode()) > MAX_SCENE_BYTES // 2:
        raise ValueError("Portable package exceeds 4 MB object budget")
    return obj
