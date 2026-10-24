"""Deterministic, reachable tabletop tasks."""

from .schema import Scene, SceneObject, Task


def example_scene():
    return Scene(
        name="Pick spoon → cup",
        objects=[
            SceneObject(
                id="spoon",
                name="Pick · spoon",
                asset="spoon",
                position=[-0.08, -0.07, 0.756],
                quaternion=[0, 0, 0, 1],
                mass=0.008,
                color="#e8c97e",
            ),
            SceneObject(
                id="cup",
                name="Place · cup",
                asset="cup",
                position=[-0.04, 0.09, 0.802],
                mass=0.10,
                color="#ef936a",
            ),
        ],
        task=Task(source="spoon", target="cup"),
    )


# Distinct arrangements, all handled by the same rehearsal/controller pipeline.
EXAMPLES = [
    (
        "kalas-cup-front",
        "01 · Spoon into cup",
        "Front placement",
        "kalas_cup",
        [-0.08, -0.07],
        [-0.04, 0.09],
        180,
        False,
    ),
    (
        "kalas-cup-left",
        "02 · Cup on the left",
        "Moved source and destination",
        "kalas_cup",
        [-0.11, -0.08],
        [-0.075, 0.075],
        170,
        False,
    ),
    (
        "kalas-cup-right",
        "03 · Cup on the right",
        "Longer cross-table transfer",
        "kalas_cup",
        [-0.10, -0.045],
        [0.005, 0.08],
        190,
        False,
    ),
    (
        "kalas-cup-near",
        "04 · Near-arm cup",
        "Closer destination",
        "kalas_cup",
        [-0.08, -0.07],
        [-0.09, 0.05],
        160,
        False,
    ),
    (
        "kalas-bowl-front",
        "05 · Spoon into bowl",
        "Open bowl destination",
        "kalas_bowl",
        [-0.08, -0.08],
        [-0.04, 0.08],
        180,
        False,
    ),
    (
        "kalas-bowl-left",
        "06 · Angled spoon into bowl",
        "Rotated source",
        "kalas_bowl",
        [-0.11, -0.085],
        [-0.075, 0.09],
        160,
        False,
    ),
    (
        "kalas-plate-front",
        "07 · Spoon onto plate",
        "Shallow plate destination",
        "kalas_plate",
        [-0.08, -0.12],
        [-0.04, 0.09],
        180,
        False,
    ),
    (
        "kalas-plate-angle",
        "08 · Angled spoon onto plate",
        "Different source orientation",
        "kalas_plate",
        [-0.11, -0.11],
        [-0.01, 0.105],
        200,
        False,
    ),
    (
        "kalas-cup-clutter",
        "09 · Cup with surrounding objects",
        "Keep clear of other utensils",
        "kalas_cup",
        [-0.08, -0.07],
        [-0.04, 0.09],
        180,
        True,
    ),
    (
        "kalas-bowl-clutter",
        "10 · Bowl with surrounding objects",
        "Transfer through a furnished scene",
        "kalas_bowl",
        [-0.08, -0.08],
        [-0.04, 0.08],
        180,
        True,
    ),
]


def example_catalog():
    return [dict(id=e[0], name=e[1], description=e[2]) for e in EXAMPLES]


legacy_example_scene = example_scene


def example_scene(example_id=None):
    if example_id is None:
        return legacy_example_scene()
    from .catalog import KALAS
    import math

    row = next((e for e in EXAMPLES if e[0] == example_id), None)
    if row is None:
        raise ValueError("Unknown example ID")
    _, name, _, asset, source, target, yaw, clutter = row
    p = KALAS[asset]
    spoon = KALAS["kalas_spoon"]
    angle = math.radians(yaw) / 2
    objects = [
        SceneObject(
            id="spoon",
            name="Pick · KALAS spoon",
            asset="kalas_spoon",
            position=[*source, 0.756],
            quaternion=[math.cos(angle), 0, 0, math.sin(angle)],
            mass=spoon["mass"],
            color=spoon["color"],
        ),
        SceneObject(
            id="cup",
            name="Place · KALAS " + p["family"],
            asset=asset,
            position=[*target, 0.752 + p["dimensions"][2] / 2],
            mass=p["mass"],
            color=p["color"],
        ),
    ]
    if clutter:
        objects.extend(
            [
                SceneObject(
                    id="other_bowl",
                    name="Other bowl",
                    asset="kalas_bowl",
                    position=[0.20, 0.16, 0.775],
                    mass=0.045,
                    color="#b6c1e4",
                ),
                SceneObject(
                    id="other_cup",
                    name="Other cup",
                    asset="kalas_cup",
                    position=[0.20, -0.16, 0.7925],
                    mass=0.03,
                    color="#9ec5b6",
                ),
            ]
        )
    return Scene(name=name, objects=objects, task=Task(source="spoon", target="cup"))
