import numpy as np
import pytest
from pydantic import ValidationError
from backend.schema import Scene
from backend.simulation import Simulation


def test_table_color_roundtrip_changes_only_tabletop_appearance():
    scene = Scene.model_validate(
        {"table": {"width": 0.8, "depth": 0.6, "height": 0.75, "color": "#336699"}}
    )
    sim = Simulation(scene)
    table = sim.model.geom("table").id
    assert np.allclose(sim.model.geom_rgba[table], [0.2, 0.4, 0.6, 1])
    assert np.allclose(
        sim.model.geom_rgba[sim.model.geom("leg_1_1").id], [0.18, 0.22, 0.25, 1]
    )
    restored = Scene.model_validate(sim.export_scene().model_dump())
    assert restored.table.color == "#336699"
    assert (
        Scene.model_validate(
            {"table": {"width": 0.8, "depth": 0.6, "height": 0.75}}
        ).table.color
        == "#b8c2bf"
    )
    with pytest.raises(ValidationError):
        Scene.model_validate({"table": {"color": "red"}})
