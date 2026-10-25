"""Export the Gym SO-101 visual/kinematic model for the connection viewer.

Run with .venv/bin/python scripts/export_robot_urdf.py after changing so101.xml.
This URDF is for display; MuJoCo remains the source of collision/dynamics rules.
"""

from pathlib import Path
import warnings
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1] / "assets/so101"


def vector(values):
    return " ".join(f"{v:.15g}" for v in values)


def origin(parent, source):
    quat = np.fromstring(source.get("quat", "1 0 0 0"), sep=" ")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # Equivalent RPY at gimbal lock.
        rpy = Rotation.from_quat(quat[[1, 2, 3, 0]]).as_euler("xyz")
    ET.SubElement(parent, "origin", xyz=source.get("pos", "0 0 0"), rpy=vector(rpy))


def export():
    source = ET.parse(ROOT / "so101.xml").getroot()
    robot = ET.Element("robot", name="so101")
    robot.append(
        ET.Comment(
            "Generated from so101.xml; Apache-2.0. Visual/kinematic description only."
        )
    )
    for material in source.findall("./asset/material"):
        node = ET.SubElement(robot, "material", name=material.get("name"))
        ET.SubElement(node, "color", rgba=material.get("rgba"))
    meshes = {
        Path(m.get("file")).stem: m.get("file") for m in source.findall("./asset/mesh")
    }

    def body(node, parent=None):
        name = node.get("name")
        link = ET.SubElement(robot, "link", name=name)
        for geom in node.findall("geom"):
            if geom.get("class") != "visual" and geom.get("name") not in {
                "wrist_camera_pcb",
                "wrist_camera_lens",
            }:
                continue
            visual = ET.SubElement(link, "visual")
            origin(visual, geom)
            geometry = ET.SubElement(visual, "geometry")
            kind = geom.get("type")
            if kind == "mesh":
                ET.SubElement(
                    geometry, "mesh", filename="assets/" + meshes[geom.get("mesh")]
                )
            elif kind == "box":
                ET.SubElement(
                    geometry,
                    "box",
                    size=vector(2 * np.fromstring(geom.get("size"), sep=" ")),
                )
            elif kind == "cylinder":
                radius, half_length = geom.get("size").split()
                ET.SubElement(
                    geometry,
                    "cylinder",
                    radius=radius,
                    length=str(2 * float(half_length)),
                )
            else:
                raise ValueError(f"Unsupported visual: {kind}")
            ET.SubElement(visual, "material", name=geom.get("material"))
        if parent is not None:
            source_joint = node.find("joint")
            joint = ET.SubElement(
                robot,
                "joint",
                name=source_joint.get("name")
                if source_joint is not None
                else name + "_fixed",
                type="revolute" if source_joint is not None else "fixed",
            )
            ET.SubElement(joint, "parent", link=parent)
            ET.SubElement(joint, "child", link=name)
            origin(joint, node)
            if source_joint is not None:
                ET.SubElement(joint, "axis", xyz=source_joint.get("axis"))
                lower, upper = source_joint.get("range").split()
                ET.SubElement(
                    joint,
                    "limit",
                    lower=lower,
                    upper=upper,
                    effort="2.94",
                    velocity="0",
                )
        for child in node.findall("body"):
            body(child, name)

    body(source.find("./worldbody/body"))
    ET.indent(robot, space="  ")
    ET.ElementTree(robot).write(
        ROOT / "so101.urdf", encoding="utf-8", xml_declaration=True
    )


if __name__ == "__main__":
    export()
