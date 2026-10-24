from backend.main import create_app
from fastapi.testclient import TestClient


def test_backend_modules_can_be_removed():
    with TestClient(create_app("gym")) as client:
        assert client.get("/api/modules").json()["enabled"] == ["gym"]
        assert client.get("/api/examples").status_code == 200
        assert client.get("/api/connection/status").status_code == 404
        assert client.post("/api/blender/create", json={}).status_code == 404


def test_connection_only_still_has_explicit_session_contract():
    with TestClient(create_app("connection")) as client:
        assert client.get("/api/connection/status").json()["connected"] is False
        assert client.post("/api/sessions").status_code == 200
        assert client.get("/api/modules").json()["enabled"] == ["connection"]


def test_unknown_only_module_config_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        create_app("missing")
