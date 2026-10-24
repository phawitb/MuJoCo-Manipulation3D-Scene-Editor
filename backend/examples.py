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
