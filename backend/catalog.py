"""Original procedural KALAS reconstructions. See docs/KALAS-SOURCES.md.

Official: bowl/plate diameters, spoon length, cup capacity. Other dimensions
are documented estimates, not metrology or manufacturer CAD.
"""

import math
import numpy as np

KALAS = {
    "kalas_bowl": dict(
        family="bowl",
        dimensions=[0.12, 0.12, 0.046],
        base=0.046,
        rim=0.060,
        thickness=0.002,
        mass=0.045,
        color="#b6c1e4",
        article="60378669",
    ),
    "kalas_cup": dict(
        family="cup",
        dimensions=[0.08, 0.08, 0.081],
        base=0.030,
        rim=0.040,
        thickness=0.002,
        mass=0.030,
        color="#eca895",
        article="40378670",
    ),
    "kalas_plate": dict(
        family="plate",
        dimensions=[0.19, 0.19, 0.024],
        base=0.079,
        rim=0.095,
        thickness=0.002,
        mass=0.065,
        color="#9ec5b6",
        article="20378671",
    ),
    "kalas_spoon": dict(
        family="spoon",
        dimensions=[0.16, 0.033, 0.008],
        grasp=-0.04,
        bowl=0.0525,
        mass=0.009,
        color="#e9cf7c",
        article="20440654",
    ),
}
KALAS_ASSETS = [
    dict(
        id=key,
        name="IKEA KALAS " + p["family"],
        category={"bowl": "Bowls", "cup": "Cups", "plate": "Plates", "spoon": "Spoons"}[
            p["family"]
        ],
        dimensions=p["dimensions"],
        mass=p["mass"],
        color=p["color"],
        description="Dimension-based reconstruction · estimated details",
        article=p["article"],
        approximate=True,
    )
    for key, p in KALAS.items()
]


def profile(obj):
    if obj.asset in KALAS:
        return KALAS[obj.asset]
    if obj.asset == "mesh":
        points = np.array(obj.mesh.vertices).reshape(-1, 3)
        dimensions = np.ptp(points, axis=0).tolist()
    else:
        dimensions = {
            "cup": [0.072, 0.072, 0.10],
            "plate": [0.14, 0.14, 0.012],
            "spoon": [0.15, 0.032, 0.008],
            "cube": [0.04, 0.04, 0.04],
        }[obj.asset]
    return dict(
        family=obj.asset,
        dimensions=dimensions,
        grasp=-0.04,
        bowl=0.05,
        rim=dimensions[0] / 2,
        thickness=0.004,
    )


def revolve(points, segments=64):
    vertices = [
        [r * math.cos(a), r * math.sin(a), z]
        for r, z in points
        for a in np.linspace(0, 2 * math.pi, segments, endpoint=False)
    ]
    faces = []
    for k in range(len(points) - 1):
        for i in range(segments):
            a = k * segments + i
            b = k * segments + (i + 1) % segments
            faces.extend([[a, b, b + segments], [a, b + segments, a + segments]])
    return np.array(vertices), np.array(faces)


def visual_mesh(asset):
    p = KALAS[asset]
    if p["family"] != "spoon":
        h = p["dimensions"][2] / 2
        b = p["base"]
        r = p["rim"]
        t = p["thickness"]
        return revolve(
            [
                (0, -h),
                (b - 0.002, -h),
                (b, -h + 0.002),
                (r - 0.001, h - 0.002),
                (r, h - 0.001),
                (r - 0.001, h),
                (r - t, h - 0.001),
                (b - t, -h + t + 0.002),
                (0, -h + t),
            ]
        )
    # Rounded flared handle and genuinely concave spoon head, with two surfaces.
    vertices = []
    faces = []
    outline = [
        (-0.08, 0),
        (-0.078, -0.007),
        (-0.07, -0.011),
        (-0.055, -0.010),
        (-0.025, -0.007),
        (0.015, -0.006),
        (0.032, -0.008),
        (0.036, 0),
        (0.032, 0.008),
        (0.015, 0.006),
        (-0.025, 0.007),
        (-0.055, 0.010),
        (-0.07, 0.011),
        (-0.078, 0.007),
    ]
    n = len(outline)
    for z in [-0.0015, 0.0015]:
        vertices.extend([[x, y, z] for x, y in outline])
    for i in range(1, n - 1):
        faces.extend([[0, i + 1, i], [n, n + i, n + i + 1]])
    for i in range(n):
        j = (i + 1) % n
        faces.extend([[i, j, n + j], [i, n + j, n + i]])
    count = 48
    rings = 10
    offset = len(vertices)
    for side in [0, 1]:
        for ring in range(rings + 1):
            radius = ring / rings
            for a in np.linspace(0, 2 * math.pi, count, endpoint=False):
                vertices.append(
                    [
                        0.0525 + 0.0275 * radius * math.cos(a),
                        0.0165 * radius * math.sin(a),
                        -0.002 + 0.006 * radius**2 - side * 0.002,
                    ]
                )
    for side in [0, 1]:
        base = offset + side * (rings + 1) * count
        for ring in range(rings):
            for i in range(count):
                a = base + ring * count + i
                b = base + ring * count + (i + 1) % count
                pair = [[a, b, a + count], [b, b + count, a + count]]
                faces.extend([f[::-1] if side else f for f in pair])
    for i in range(count):
        a = offset + rings * count + i
        b = offset + rings * count + (i + 1) % count
        shift = (rings + 1) * count
        faces.extend([[a, a + shift, b], [b, a + shift, b + shift]])
    return np.array(vertices), np.array(faces)


def collision_shapes(asset):
    p = KALAS[asset]
    if p["family"] == "spoon":
        return [
            ("box", [0.05, 0.007, 0.0015], [-0.028, 0, 0], {}),
            ("ellipsoid", [0.0275, 0.0165, 0.003], [0.0525, 0, 0], {}),
        ]
    h = p["dimensions"][2]
    base = p["base"]
    rim = p["rim"]
    t = p["thickness"]
    shapes = [("cylinder", [base, t / 2], [0, 0, -h / 2 + t / 2], {})]
    # Segmented sloped walls keep cavities open while matching the tapered shell.
    n = 32
    bottom = -h / 2 + t
    top = h / 2 - t / 2
    mid = (bottom + top) / 2
    slope = math.atan2(rim - base, top - bottom)
    for i in range(n):
        a = 2 * math.pi * i / n
        radius = (base + rim) / 2 - t / 2
        # Euler local Y tilt tips the wall radially outward toward its rim.
        shapes.append(
            (
                "box",
                [
                    t / 2,
                    rim * math.tan(math.pi / n) * 1.02,
                    math.hypot(top - bottom, rim - base) / 2,
                ],
                [radius * math.cos(a), radius * math.sin(a), mid],
                dict(euler=f"0 {slope} {a}"),
            )
        )
    return shapes
