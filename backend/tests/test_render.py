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
