import numpy as np
import pytest
from backend.schema import ASSETS, Scene, SceneObject
from backend.simulation import Simulation


@pytest.mark.parametrize(
    "asset,dimensions",
    [
        ("kalas_bowl", [0.12, 0.12, 0.046]),
        ("kalas_cup", [0.08, 0.08, 0.081]),
        ("kalas_spoon", [0.16, 0.033, 0.008]),
        ("kalas_plate", [0.19, 0.19, 0.024]),
    ],
)
def test_kalas_dimensions_compile_and_settle(asset, dimensions):
    metadata = next((a for a in ASSETS if a["id"] == asset), None)
    assert metadata is not None
    assert metadata["dimensions"] == dimensions
    sim = Simulation(
        Scene(objects=[SceneObject(id="item", asset=asset, position=[0.1, 0.15, 1])])
    )
    assert any(g["owner"] == "item" and g["kind"] == "mesh" for g in sim.geometry())
    sim.step(1000)
    assert np.isfinite(sim.data.qpos).all()
    assert 0.75 < sim.data.body("object_item").xpos[2] < 0.85
    assert sim.snapshot()["meshes"]


def test_kalas_container_collision_has_open_cavity():
    import mujoco

    for asset, height in [
        ("kalas_cup", 0.081),
        ("kalas_bowl", 0.046),
        ("kalas_plate", 0.024),
    ]:
        sim = Simulation(
            Scene(
                objects=[
                    SceneObject(
                        id="vessel",
                        asset=asset,
                        position=[0.1, 0.15, 0.75 + height / 2],
                    )
                ]
            )
        )
        geom_id = np.array([-1], dtype=np.int32)
        distance = mujoco.mj_ray(
            sim.model,
            sim.data,
            np.array([0.1, 0.15, 0.95]),
            np.array([0.0, 0.0, -1.0]),
            np.array([0, 0, 0, 1, 0, 0], dtype=np.uint8),
            1,
            -1,
            geom_id,
        )
        assert distance > 0.95 - (0.75 + 0.01), (asset, distance)
        assert distance < 0.25


def test_visual_shell_does_not_reduce_requested_body_mass():
    sim = Simulation(
        Scene(objects=[SceneObject(id="cup", asset="kalas_cup", mass=0.03)])
    )
    assert sim.model.body("object_cup").mass[0] == pytest.approx(0.03, abs=1e-10)
