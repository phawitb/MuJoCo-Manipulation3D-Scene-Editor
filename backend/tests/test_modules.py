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


def test_loading_scene_replaces_previous_objects_without_new_session():
    from backend.schema import Scene, SceneObject

    with TestClient(create_app("gym")) as client:
        initial = client.post("/api/sessions").json()
        sid = initial["sessionId"]
        first = Scene(objects=[SceneObject(id="old-cube", asset="cube")]).model_dump()
        response = client.post(
            f"/api/sessions/{sid}/command", json={"type": "load", "scene": first}
        )
        assert response.status_code == 200
        response = client.post(
            f"/api/sessions/{sid}/command",
            json={"type": "load", "scene": Scene().model_dump()},
        )
        assert response.status_code == 200
        assert response.json()["scene"]["objects"] == []
        assert response.json()["sessionId"] == sid
        assert len(client.get("/api/sessions").json()) == 1


def test_scene_replacement_guard_is_shared_by_http_and_websocket():
    class ConnectionGuard:
        def __init__(self):
            self.calls = []

        def replace_scene(self, session, command):
            self.calls.append((session.id, command.type))
            return session.execute(command)

    app = create_app("gym")
    guard = ConnectionGuard()
    with TestClient(app) as client:
        app.state.connection = guard
        sid = client.post("/api/sessions").json()["sessionId"]
        assert (
            client.post(
                f"/api/sessions/{sid}/command", json={"type": "reset"}
            ).status_code
            == 200
        )
        with client.websocket_connect(f"/ws?session={sid}") as socket:
            socket.receive_json()
            socket.send_json({"type": "reset", "requestId": "replace"})
            response = socket.receive_json()
            assert response["requestId"] == "replace"
        assert guard.calls == [(sid, "reset"), (sid, "reset")]
