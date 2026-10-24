from fastapi.testclient import TestClient
from backend.main import app
from backend.schema import Scene


def test_back_camera_survives_edits_and_legacy_scene_roundtrip():
    with TestClient(app) as client:
        packet = client.post("/api/sessions").json()
        sid = packet["sessionId"]
        value = {
            "position": [-0.4, 0.1, 1.6],
            "target": [0.1, 0, 0.78],
            "fov": 55,
            "zoom": 1,
        }
        response = client.post(
            f"/api/sessions/{sid}/command",
            json={
                "type": "camera",
                "camera": "back",
                "value": value,
            },
        )
        assert response.status_code == 200
        scene = response.json()["scene"]
        assert scene["cameras"]["back"] == value
        assert Scene.model_validate(scene).cameras["back"].position == value["position"]
        del scene["cameras"]["back"]
        restored = Scene.model_validate(scene)
        back = restored.cameras["back"]
        assert back.position[2] > restored.robot.position[2] + 0.5
        assert back.position[0] <= restored.robot.position[0]
        assert back.target[0] > back.position[0]
        assert back.target[2] < back.position[2]
        assert restored.cameras["front"].model_dump() == scene["cameras"]["front"]
