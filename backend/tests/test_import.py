import numpy as np
import pytest
import trimesh
from backend.importer import import_object
from backend.schema import Scene
from backend.simulation import Simulation


@pytest.mark.parametrize("fmt", ["stl", "obj", "glb"])
def test_import_real_mesh_and_portable_roundtrip(fmt):
    raw = trimesh.creation.box().export(file_type=fmt)
    if isinstance(raw, str):
        raw = raw.encode()
    obj = import_object(raw, f"block.{fmt}", 0.06)
    assert obj.asset == "mesh"
    assert np.allclose(np.ptp(np.array(obj.mesh.vertices).reshape(-1, 3), axis=0), 0.06)
    scene = Scene(objects=[obj])
    s = Simulation(scene)
    assert any(g["kind"] == "mesh" and g["owner"] == obj.id for g in s.geometry())
    restored = Simulation(Scene.model_validate_json(s.export_scene().model_dump_json()))
    assert restored.snapshot()["meshes"]
    restored.step(500)
    assert restored.data.body(f"object_{obj.id}").xpos[2] > 0.76


def test_import_rejects_bad_file_and_flat_geometry():
    for data, name, size in [
        (b"bad", "bad.stl", 0.1),
        (b"no", "foo.exe", 0.1),
        (b"x" * 10_000_001, "a.stl", 0.1),
        (b"a", "a.obj", float("nan")),
    ]:
        with pytest.raises(ValueError):
            import_object(data, name, size)
    flat = b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
    with pytest.raises(ValueError, match="volume|solid|thickness"):
        import_object(flat, "flat.obj", 0.1)


def test_cumulative_import_budget_keeps_every_accepted_save_reopenable():
    import json
    from backend.sessions import Command, Session
    from backend.importer import MAX_SCENE

    mesh = trimesh.creation.icosphere(subdivisions=5, radius=0.05)
    obj = import_object(mesh.export(file_type="glb"), "sphere.glb", 0.1)
    session = Session()
    accepted = 0
    for index in range(10):
        before = session.sim.export_scene().model_dump()
        revision = session.sim.revision
        item = obj.model_dump()
        item["id"] = f"sphere{index}"
        try:
            session.execute(Command(type="object_add", object=item))
        except ValueError as exc:
            assert "size budget" in str(exc)
            assert session.sim.revision == revision
            assert session.sim.export_scene().model_dump() == before
            break
        accepted += 1
        scene = session.sim.export_scene().model_dump()
        saved = json.dumps(
            {"version": 1, "scene": scene, "cameras": scene["cameras"]}, indent=2
        )
        assert len(saved.encode()) < MAX_SCENE
        reloaded = json.loads(saved)["scene"]
        command = json.dumps({"type": "load", "scene": reloaded}).encode()
        assert len(command) < MAX_SCENE
        session.execute(Command.model_validate_json(command))
    assert 1 <= accepted < 10
