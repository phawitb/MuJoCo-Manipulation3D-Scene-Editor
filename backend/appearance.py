"""Portable visual recipes, deterministic randomization, and shared texture pixels."""

import base64
import colorsys
import io
import random
import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Annotated, Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Pattern = Literal[
    "solid", "checker", "stripes", "dots", "wood", "terrazzo", "tiles", "noise"
]
Group = Literal["robot", "table", "environment", "lighting", "objects"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Surface(Strict):
    pattern: Pattern = "solid"
    secondary: Color = "#e8e4dc"
    repeat: float = Field(default=4, ge=1, le=24)
    roughness: float = Field(default=0.7, ge=0.05, le=1)
    metallic: float = Field(default=0, ge=0, le=1)


class Randomization(Strict):
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    groups: list[Group] = Field(
        default_factory=lambda: [
            "robot",
            "table",
            "environment",
            "lighting",
            "objects",
        ],
        max_length=5,
    )
    strength: Literal["mild", "balanced", "wide"] = "balanced"


class Appearance(Strict):
    generator: Literal[1] = 1
    last_randomization: Randomization | None = None
    robot_color: Color = "#ffd11f"
    motor_color: Color = "#1a1a1a"
    leg_color: Color = "#2e3840"
    floor_color: Color = "#13171c"
    wall_color: Color = "#a8b1b6"
    background: Color = "#202a30"
    robot: Surface = Field(
        default_factory=lambda: Surface(roughness=0.65, metallic=0.12)
    )
    table: Surface = Field(default_factory=lambda: Surface(roughness=0.9))
    floor: Surface = Field(default_factory=lambda: Surface(roughness=1))
    wall: Surface = Field(default_factory=Surface)
    environment: Literal["open", "studio", "room", "warehouse", "panels"] = "open"
    key_color: Color = "#ffffff"
    key_intensity: float = Field(default=1, ge=0, le=2.5)
    fill_intensity: float = Field(default=0.4, ge=0, le=1.5)
    ambient: float = Field(default=0.35, ge=0.05, le=1)
    light_azimuth: float = Field(default=-45, ge=-180, le=180)
    light_elevation: float = Field(default=60, ge=15, le=85)
    shadows: bool = True


def rgb(color):
    return [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]


def light_position(a):
    az, el = np.deg2rad([a.light_azimuth, a.light_elevation])
    return [
        float(2.5 * np.cos(el) * np.cos(az)),
        float(2.5 * np.cos(el) * np.sin(az)),
        float(0.75 + 2.5 * np.sin(el)),
    ]


@lru_cache(maxsize=128)
def texture_png(pattern, color, secondary):
    """One repeatable 128px tile; same pixels are used by both renderers."""
    n = 128
    y, x = np.mgrid[0:n, 0:n] / n
    rng = np.random.default_rng(20261029)
    if pattern == "checker":
        mask = ((x >= 0.5) ^ (y >= 0.5)).astype(float)
    elif pattern == "stripes":
        mask = (x > 0.5).astype(float)
    elif pattern == "dots":
        mask = ((x - 0.5) ** 2 + (y - 0.5) ** 2 < 0.08).astype(float)
    elif pattern == "wood":
        mask = (
            0.35
            + 0.25 * np.sin(2 * np.pi * (x * 6 + 0.3 * np.sin(2 * np.pi * y)))
            + 0.12 * rng.random((n, n))
        )
    elif pattern == "terrazzo":
        mask = np.zeros((n, n))
        for _ in range(80):
            cx, cy, radius = rng.random(3)
            dx, dy = (
                np.minimum(abs(x - cx), 1 - abs(x - cx)),
                np.minimum(abs(y - cy), 1 - abs(y - cy)),
            )
            mask[dx**2 + dy**2 < (0.008 + radius * 0.045) ** 2] = (
                0.3 + 0.7 * rng.random()
            )
    elif pattern == "tiles":
        mask = ((x < 0.035) | (y < 0.035)).astype(float)
    elif pattern == "noise":
        mask = rng.random((n, n))
    else:
        mask = np.zeros((n, n))
    pixels = (
        np.array(rgb(color))[None, None, :] * (1 - mask[..., None])
        + np.array(rgb(secondary))[None, None, :] * mask[..., None]
    ) * 255
    out = io.BytesIO()
    Image.fromarray(np.uint8(np.clip(pixels, 0, 255))).save(out, format="PNG")
    return out.getvalue()


def surfaces(scene):
    a = scene.appearance
    return {
        "look_robot": (a.robot_color, a.robot),
        "look_motor": (a.motor_color, Surface(roughness=0.65)),
        "look_table": (scene.table.color, a.table),
        "look_legs": (a.leg_color, Surface(metallic=0.3)),
        "look_floor": (a.floor_color, a.floor),
        "look_wall": (a.wall_color, a.wall),
    }


def render_materials(scene):
    return {
        name: dict(
            color=color,
            **surface.model_dump(),
            texture=(
                "data:image/png;base64,"
                + base64.b64encode(
                    texture_png(surface.pattern, color, surface.secondary)
                ).decode()
            )
            if surface.pattern != "solid"
            else None,
        )
        for name, (color, surface) in surfaces(scene).items()
    }


def apply_texture_pixels(model, scene):
    for name, (color, surface) in surfaces(scene).items():
        if surface.pattern == "solid":
            continue
        tid = model.texture(name + "_tex").id
        data = np.array(
            Image.open(
                io.BytesIO(texture_png(surface.pattern, color, surface.secondary))
            )
        )
        start = model.tex_adr[tid]
        model.tex_data[start : start + data.size] = data.reshape(-1)


def decorate_xml(root, scene):
    a = scene.appearance
    asset, world = root.find("asset"), root.find("worldbody")
    for name, (color, surface) in surfaces(scene).items():
        # Preserve the original default leg shade exactly.
        base = (
            [0.18, 0.22, 0.25]
            if name == "look_legs" and color == "#2e3840"
            else rgb(color)
        )
        attrs = dict(
            name=name,
            rgba=" ".join(map(str, base + [1])),
            shininess=str(1 - surface.roughness),
            specular=str(0.2 + 0.6 * surface.metallic),
        )
        if surface.pattern != "solid":
            ET.SubElement(
                asset,
                "texture",
                name=name + "_tex",
                type="2d",
                builtin="checker",
                width="128",
                height="128",
                rgb1="1 1 1",
                rgb2="0 0 0",
            )
            attrs.update(
                texture=name + "_tex",
                rgba="1 1 1 1",
                texrepeat=f"{surface.repeat} {surface.repeat}",
                texuniform="false",
            )
        ET.SubElement(asset, "material", **attrs)
    for geom in world.iter("geom"):
        name = geom.get("name", "")
        if geom.get("class") == "visual":
            old = geom.get("material", "")
            geom.set("material", "look_motor" if "sts3215" in old else "look_robot")
        elif name == "table":
            geom.set("material", "look_table")
        elif name == "floor":
            geom.set("material", "look_floor")
        elif name.startswith("leg_"):
            geom.set("material", "look_legs")
        material = geom.get("material", "")
        if material.startswith("look_"):
            # Explicit geom RGBA overrides materials in MuJoCo. Textured
            # materials need a white multiplier because their pixels are colored.
            geom.set("rgba", asset.find(f"material[@name='{material}']").get("rgba"))
    visual = root.find("visual")
    ET.SubElement(
        visual,
        "headlight",
        active="1",
        diffuse="0 0 0",
        ambient=" ".join([str(a.ambient)] * 3),
        specular="0 0 0",
    )
    ET.SubElement(visual, "rgba", haze=" ".join(map(str, rgb(a.background) + [1])))
    ET.SubElement(
        asset,
        "texture",
        name="look_sky",
        type="skybox",
        builtin="flat",
        rgb1=" ".join(map(str, rgb(a.background))),
        width="64",
        height="384",
    )
    pos = light_position(a)
    direction = [-pos[0], -pos[1], 0.75 - pos[2]]
    ET.SubElement(
        world,
        "light",
        name="look_key",
        pos=" ".join(map(str, pos)),
        dir=" ".join(map(str, direction)),
        directional="true",
        diffuse=" ".join(str(v * a.key_intensity) for v in rgb(a.key_color)),
        specular=".3 .3 .3",
        castshadow=str(a.shadows).lower(),
    )
    ET.SubElement(
        world,
        "light",
        name="look_fill",
        pos="-2 2 3",
        dir="2 -2 -2",
        directional="true",
        diffuse=" ".join([str(a.fill_intensity)] * 3),
        castshadow="false",
    )

    def box(name, pos, size, material="look_wall"):
        ET.SubElement(
            world,
            "geom",
            name="decor_" + name,
            type="box",
            pos=" ".join(map(str, pos)),
            size=" ".join(map(str, size)),
            material=material,
            contype="0",
            conaffinity="0",
            group="1",
            mass="0",
        )

    if a.environment != "open":
        box("back", [0, 2.3, 1.5], [3, 0.04, 1.5])
    if a.environment in ("room", "warehouse", "studio"):
        box("side", [-2.3, 0, 1.5], [0.04, 2.3, 1.5])
    if a.environment == "room":
        for x in (-1.4, 0, 1.4):
            box(f"window_{x}", [x, 2.24, 1.7], [0.45, 0.015, 0.6], "look_floor")
        box("sill", [0, 2.18, 1.05], [2.3, 0.1, 0.04], "look_legs")
    if a.environment == "warehouse":
        for x in (-1.6, 0, 1.6):
            for z in (0.3, 1.1, 1.9):
                box(f"shelf_{x}_{z}", [x, 1.8, z], [0.65, 0.25, 0.035], "look_legs")
                for dx in (-0.35, 0.35):
                    box(
                        f"box_{x}_{z}_{dx}",
                        [x + dx, 1.8, z + 0.2],
                        [0.22, 0.18, 0.16],
                        "look_table",
                    )
            for dx in (-0.65, 0.65):
                box(
                    f"post_{x}_{dx}",
                    [x + dx, 1.8, 1.2],
                    [0.025, 0.25, 1.2],
                    "look_legs",
                )
    if a.environment == "panels":
        for i in range(7):
            box(
                f"panel_{i}",
                [-2.1 + i * 0.7, 2.2, 1.4],
                [0.28, 0.06, 1.35],
                "look_robot" if i % 2 else "look_table",
            )


def randomize_scene(scene, config):
    result = scene.model_copy(deep=True)
    a = result.appearance
    # Per-group streams make locked groups independent of selection order.
    for group in dict.fromkeys(config.groups):
        rng = random.Random(f"appearance-v1:{config.seed}:{group}")
        span = {"mild": 0.15, "balanced": 0.55, "wide": 1}[config.strength]

        def color():
            h, s, v = (
                rng.random(),
                rng.uniform(0.1, 0.25 + span * 0.65),
                rng.uniform(0.35, 0.95),
            )
            return "#" + "".join(
                f"{round(c * 255):02x}" for c in colorsys.hsv_to_rgb(h, s, v)
            )

        def surface():
            patterns = (
                ["solid", "wood", "tiles"]
                if config.strength == "mild"
                else [
                    "solid",
                    "checker",
                    "stripes",
                    "dots",
                    "wood",
                    "terrazzo",
                    "tiles",
                    "noise",
                ]
            )
            return Surface(
                pattern=rng.choice(patterns),
                secondary=color(),
                repeat=round(rng.uniform(1, 3 + span * 17), 1),
                roughness=round(rng.uniform(0.25, 1), 2),
                metallic=round(rng.uniform(0, span * 0.7), 2),
            )

        if group == "robot":
            a.robot_color, a.motor_color, a.robot = color(), color(), surface()
        elif group == "table":
            result.table.color, a.leg_color, a.table = color(), color(), surface()
        elif group == "environment":
            a.environment = rng.choice(
                ["open", "studio", "room", "warehouse", "panels"]
            )
            a.background, a.floor_color, a.wall_color = color(), color(), color()
            a.floor, a.wall = surface(), surface()
        elif group == "lighting":
            a.key_color = rng.choice(["#ffffff", "#fff1d6", "#d6eaff", "#ffe0ce"])
            a.key_intensity = round(rng.uniform(0.65, 1 + span * 1.3), 2)
            a.fill_intensity = round(rng.uniform(0.1, 0.8), 2)
            a.ambient = round(rng.uniform(0.15, 0.55), 2)
            a.light_azimuth, a.light_elevation = (
                round(rng.uniform(-180, 180)),
                round(rng.uniform(20, 80)),
            )
            a.shadows = rng.choice([True, False]) if config.strength == "wide" else True
        elif group == "objects":
            for obj in sorted(result.objects, key=lambda obj: obj.id):
                obj.color = color()
    a.last_randomization = config.model_copy(deep=True)
    return result


def presets():
    configs = [
        ("baseline", "Original studio", "Neutral starting point", "#b8c2bf", {}),
        (
            "daylight",
            "Daylight lab",
            "Cool walls · bright diffuse light",
            "#e2e5df",
            dict(
                environment="room",
                background="#b9d3e5",
                floor_color="#8e9a9e",
                wall_color="#e0e6e9",
                key_color="#e5f2ff",
                ambient=0.5,
                table=dict(pattern="tiles", secondary="#b4bec1", repeat=8),
            ),
        ),
        (
            "warm",
            "Warm workshop",
            "Oak grain · warm directional light",
            "#a57745",
            dict(
                environment="warehouse",
                background="#514039",
                floor_color="#58534a",
                wall_color="#bcae99",
                table=dict(pattern="wood", secondary="#60452e", repeat=3),
                key_color="#ffdbab",
                light_azimuth=35,
            ),
        ),
        (
            "industrial",
            "Industrial bay",
            "Steel finishes · concrete floor",
            "#7c9298",
            dict(
                environment="warehouse",
                robot_color="#f1792e",
                floor_color="#70777c",
                floor=dict(pattern="noise", secondary="#a1a5a7", repeat=12),
                table=dict(roughness=0.3, metallic=0.65),
                wall_color="#52616b",
            ),
        ),
        (
            "color",
            "Color lab",
            "Bold panels · checker worktop",
            "#668ad5",
            dict(
                environment="panels",
                robot_color="#e78dbe",
                motor_color="#4c3a6a",
                background="#ddd2e5",
                floor_color="#c2b8d2",
                table=dict(pattern="checker", secondary="#f4e6c1", repeat=6),
                wall_color="#8193af",
            ),
        ),
        (
            "terrazzo",
            "Terrazzo room",
            "Speckled surfaces · soft warm light",
            "#d7c6b6",
            dict(
                environment="room",
                table=dict(pattern="terrazzo", secondary="#6b817c", repeat=5),
                floor_color="#a1b2a5",
                floor=dict(pattern="tiles", secondary="#e0ddd2", repeat=10),
                wall_color="#eadac8",
                key_color="#fff3df",
                ambient=0.5,
            ),
        ),
    ]
    return [
        dict(
            id=id,
            name=name,
            description=description,
            tableColor=table,
            appearance=Appearance.model_validate(config).model_dump(),
        )
        for id, name, description, table, config in configs
    ]
