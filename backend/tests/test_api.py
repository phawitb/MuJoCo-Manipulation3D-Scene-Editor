from fastapi.testclient import TestClient
from backend.main import app


def receive(ws, kind):
    for _ in range(50):
        data = ws.receive_json()
        if data["type"] == kind:
            return data
    raise AssertionError(f"No {kind} packet")


def test_http_metadata_and_websocket_controls():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["engine"] == "MuJoCo"
        assert len(client.get("/api/assets").json()) == 4
        assert len(client.get("/api/meshes").json()) >= 10
        with client.websocket_connect("/ws") as ws:
            initial = receive(ws, "snapshot")
            assert initial["scene"]["objects"] == [] and not initial["running"]
            ws.send_json({"type": "step", "requestId": "s"})
            stepped = receive(ws, "snapshot")
            assert stepped["time"] > 0
            ws.send_json({"type": "physics"})
            assert receive(ws, "snapshot")["running"]
            ws.send_json({"type": "pause"})
            paused = receive(ws, "snapshot")
            assert not paused["running"]
            ws.send_json(
                {"type": "load", "scene": {"objects": [{"id": "bad", "mass": -1}]}}
            )
            assert receive(ws, "error")["message"]
            ws.send_json({"type": "reset"})
            assert receive(ws, "snapshot")["time"] == 0
            ws.send_json({"type": "unknown"})
            assert receive(ws, "error")["message"]


def test_edit_rejected_during_run_and_revision_conflict():
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        snap = receive(ws, "snapshot")
        ws.send_json({"type": "load", "scene": snap["scene"], "revision": 999})
        assert "stale" in receive(ws, "error")["message"].lower()
        ws.send_json({"type": "physics"})
        receive(ws, "snapshot")
        ws.send_json({"type": "load", "scene": snap["scene"]})
        assert "pause" in receive(ws, "error")["message"].lower()


def test_malformed_json_does_not_destroy_session():
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        initial = receive(ws, "snapshot")
        ws.send_text("{broken")
        assert receive(ws, "error")["message"]
        ws.send_json({"type": "snapshot"})
        assert receive(ws, "snapshot")["scene"] == initial["scene"]


def test_separate_websocket_sessions_are_isolated():
    with (
        TestClient(app) as client,
        client.websocket_connect("/ws") as a,
        client.websocket_connect("/ws") as b,
    ):
        sa = receive(a, "snapshot")
        receive(b, "snapshot")
        sa["scene"]["objects"] = [{"id": "cup1"}]
        a.send_json({"type": "load", "scene": sa["scene"]})
        assert len(receive(a, "snapshot")["scene"]["objects"]) == 1
        b.send_json({"type": "snapshot"})
        assert receive(b, "snapshot")["scene"]["objects"] == []


def test_workspace_boundary_pauses_stream_and_preserves_loadable_scene():
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        initial = receive(ws, "snapshot")
        initial["scene"]["objects"] = [
            {
                "id": "ghost",
                "asset": "cube",
                "position": [0, 0.1, 1],
                "collision": False,
            }
        ]
        ws.send_json({"type": "load", "scene": initial["scene"]})
        receive(ws, "snapshot")
        ws.send_json({"type": "physics"})
        paused = receive(ws, "snapshot")
        while paused["running"]:
            paused = receive(ws, "snapshot")
        assert not paused["running"]
        assert paused["scene"]["objects"][0]["position"][2] >= -5
        assert "workspace" in paused["warning"]
        ws.send_json({"type": "load", "scene": paused["scene"]})
        assert len(receive(ws, "snapshot")["scene"]["objects"]) == 1
