"""Reconstruct namespaced rigid package geometry in the editor model."""

import xml.etree.ElementTree as ET


def nums(values):
    return " ".join(str(float(v)) for v in values)


def add_package(root, obj):
    pkg = obj.package
    s = obj.scale
    prefix = "pkg_" + obj.id
    asset = root.find("asset")
    for i, mesh in enumerate(pkg.meshes):
        ET.SubElement(
            asset,
            "mesh",
            name=f"{prefix}_mesh_{i}",
            vertex=nums([v * s for v in mesh.vertices]),
            face=" ".join(map(str, mesh.faces)),
        )
    body = ET.SubElement(
        root.find("worldbody"),
        "body",
        name="object_" + obj.id,
        pos=nums(obj.position),
        quat=nums(obj.quaternion),
    )
    ET.SubElement(body, "freejoint")
    ET.SubElement(
        body,
        "inertial",
        mass=str(obj.mass),
        pos=nums([v * s for v in pkg.com]),
        fullinertia=nums([v * s * s * obj.mass / pkg.mass for v in pkg.inertia]),
    )
    for i, g in enumerate(pkg.geoms):
        color = (
            ([int(obj.color[k : k + 2], 16) / 255 for k in (1, 3, 5)] + [g.rgba[3]])
            if obj.package_color_override
            else g.rgba
        )
        attrs = dict(
            name=f"obj_{obj.id}_{i}",
            type=g.kind,
            pos=nums([v * s for v in g.position]),
            quat=nums(g.quaternion),
            rgba=nums(color),
            mass="0",
            group=str(g.group),
            contype=str(g.contype if obj.collision else 0),
            conaffinity=str(g.conaffinity if obj.collision else 0),
            condim=str(g.condim),
            friction=nums(
                obj.friction if obj.package_friction_override else g.friction
            ),
            solref=nums(g.solref),
            solimp=nums(g.solimp),
            priority=str(g.priority),
            solmix=str(g.solmix),
            margin=str(g.margin * s),
            gap=str(g.gap * s),
        )
        if g.kind == "mesh":
            attrs["mesh"] = f"{prefix}_mesh_{g.mesh}"
        else:
            attrs["size"] = nums([v * s for v in g.size])
        if g.material:
            mat = f"{prefix}_material_{i}"
            ET.SubElement(
                asset,
                "material",
                name=mat,
                rgba=nums(color),
                **{k: str(v) for k, v in g.material.items()},
            )
            attrs["material"] = mat
        ET.SubElement(body, "geom", **attrs)
    for i, position in enumerate(pkg.sites.values()):
        ET.SubElement(
            body,
            "site",
            name=f"{prefix}_site_{i}",
            pos=nums([v * s for v in position]),
            size=".001",
            group="4",
        )
