"""Durable reusable assets must retain source physics without scene identity."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.tests.test_package_import import read_package


def test_library_survives_restart_and_preserves_compound_physics(tmp_path):
    from backend.import_library import ImportLibrary

    obj = read_package()
    obj.scale = 1.3
    obj.mass = 0.06
    obj.package_friction_override = True
    obj.friction = [0.8, 0.002, 0.0003]
    library = ImportLibrary(tmp_path)
    summary = library.save(obj)
    assert summary["category"] == "Imported"
    assert summary["dimensions"] == pytest.approx([0.065, 0.039, 0.013])
    assert "package" not in summary
    restored = ImportLibrary(tmp_path).get(summary["id"])
    assert restored.package.model_dump() == obj.package.model_dump()
    assert restored.mass == 0.06
    assert restored.scale == 1.3
    assert restored.friction == [0.8, 0.002, 0.0003]
    assert restored.package_friction_override is True
    assert restored.position == [0, 0, 0]
    assert restored.quaternion == [1, 0, 0, 0]
    assert ImportLibrary(tmp_path).list() == [summary]


def test_content_dedup_ignores_scene_identity_but_retains_physics_variants(tmp_path):
    from backend.import_library import ImportLibrary

    obj = read_package()
    library = ImportLibrary(tmp_path)
    first = library.save(obj)
    obj.id = "new_copy"
    obj.name = "Renamed scene copy"
    obj.position = [0.2, 0.1, 0.8]
    obj.quaternion = [0, 0, 0, 1]
    assert library.save(obj) == first
    assert library.get(first["id"]).name == "sensor"
    obj.mass = 0.08
    assert library.save(obj)["id"] != first["id"]
    assert len(library.list()) == 2


def test_library_bounds_reject_new_assets_without_losing_saved_objects(tmp_path):
    from backend.import_library import ImportLibrary

    library = ImportLibrary(tmp_path, max_assets=1, max_bytes=10_000_000)
    obj = read_package()
    first = library.save(obj)
    assert library.save(obj) == first
    obj.mass = 0.08
    with pytest.raises(ValueError, match="full"):
        library.save(obj)
    assert len(ImportLibrary(tmp_path).list()) == 1
    with pytest.raises(ValueError, match="full"):
        ImportLibrary(tmp_path / "tiny", max_bytes=1).save(obj)


def test_api_only_saves_placed_imports_and_survives_app_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("SO101_IMPORT_LIBRARY", str(tmp_path))
    obj = read_package()
    with TestClient(app) as client:
        assert client.get("/api/imported-assets").json() == []
        sid = client.post("/api/sessions").json()["sessionId"]
        url = f"/api/imported-assets?session_id={sid}&object_id={obj.id}"
        assert client.post(url).status_code == 404
        placed = client.post(
            f"/api/sessions/{sid}/command",
            json={"type": "object_add", "object": obj.model_dump()},
        )
        assert placed.status_code == 200
        saved = client.post(url)
        assert saved.status_code == 200
        asset_id = saved.json()["id"]
        assert client.post(url).json()["id"] == asset_id
        assert len(client.get("/api/assets").json()) == 8
    with TestClient(app) as client:
        assert len(client.get("/api/imported-assets").json()) == 1
        assert (
            client.get(f"/api/imported-assets/{asset_id}").json()["package"]
            == obj.package.model_dump()
        )
        assert client.get("/api/imported-assets/imported_unknown").status_code == 404


def test_preview_does_not_write_library(tmp_path, monkeypatch):
    import base64
    from backend.tests.test_package_import import fixture_files

    monkeypatch.setenv("SO101_IMPORT_LIBRARY", str(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/api/import/package",
            json={
                "files": [
                    {"path": name, "data": base64.b64encode(data).decode()}
                    for name, data in fixture_files().items()
                ]
            },
        )
        assert response.status_code == 200
        assert client.get("/api/imported-assets").json() == []
        assert not list(tmp_path.glob("*.json"))


def test_atomic_write_failure_keeps_previous_library_intact(tmp_path, monkeypatch):
    import os
    from backend.import_library import ImportLibrary

    obj = read_package()
    library = ImportLibrary(tmp_path)
    saved = library.save(obj)
    obj.mass = 0.07

    def disk_failure(*args):
        raise OSError("Disk unavailable")

    monkeypatch.setattr(os, "replace", disk_failure)
    with pytest.raises(OSError, match="Disk unavailable"):
        library.save(obj)
    assert ImportLibrary(tmp_path).list() == [saved]
    assert not list(tmp_path.glob(".import-*"))


def test_mesh_library_retains_portable_vertices_faces_and_source(tmp_path):
    import trimesh
    from backend.importer import import_object
    from backend.import_library import ImportLibrary

    obj = import_object(
        trimesh.creation.box().export(file_type="glb"), "block.glb", 0.06
    )
    library = ImportLibrary(tmp_path)
    summary = library.save(obj)
    restored = ImportLibrary(tmp_path).get(summary["id"])
    assert restored.mesh.model_dump() == obj.mesh.model_dump()
    assert restored.mesh.filename == "block.glb"
    assert summary["dimensions"] == pytest.approx([0.06, 0.06, 0.06])
