import io
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app


def test_agent_can_get_actual_wrist_camera_png():
    with TestClient(app) as c:
        sid = c.post("/api/sessions").json()["sessionId"]
        c.post(f"/api/sessions/{sid}/command", json={"type": "example"})
        result = c.get(f"/api/sessions/{sid}/image?view=wrist")
        assert result.status_code == 200
        assert result.headers["content-type"] == "image/png"
        image = Image.open(io.BytesIO(result.content))
        assert image.size == (640, 480)
        assert len(image.getcolors(640 * 480)) > 100


def test_native_top_keeps_robot_side_below_center():
    import numpy as np

    with TestClient(app) as c:
        sid = c.post("/api/sessions").json()["sessionId"]
        result = c.get(f"/api/sessions/{sid}/image?view=top")
        assert result.status_code == 200
        pixels = np.array(
            Image.open(io.BytesIO(result.content)).convert("RGB"), dtype=float
        )
        # The empty default scene has only one yellow item: the robot on -X.
        r, g, b = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
        robot = (r > 100) & (g > 70) & (b < r * 0.5) & (b < g * 0.6)
        rows, _ = np.nonzero(robot)
        assert len(rows) > 100
        assert rows.mean() > pixels.shape[0] / 2
