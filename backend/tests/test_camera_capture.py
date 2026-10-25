"""Exercise the capture worker against camera startup/exposure behavior."""

import io
import sys
from types import SimpleNamespace

import pytest

from backend.modules.connection.cameras import CAPTURE


@pytest.mark.parametrize("fails_after_startup", [False, True])
def test_capture_waits_for_exposure_and_rejects_lost_camera(monkeypatch, fails_after_startup):
    import time

    elapsed = [0.0]
    released = []

    class Camera:
        def isOpened(self):
            return True

        def set(self, *args):
            pass

        def read(self):
            elapsed[0] += 0.1
            if fails_after_startup and elapsed[0] >= 0.3:
                return False, None
            return True, b"exposed" if elapsed[0] >= 0.5 else b"black"

        def release(self):
            released.append(True)

    cv2 = SimpleNamespace(
        VideoCapture=lambda _: Camera(),
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        IMWRITE_JPEG_QUALITY=1,
        imencode=lambda ext, frame, opts: (
            True, SimpleNamespace(tobytes=lambda: b"\xff\xd8" + frame)
        ),
    )
    output = io.BytesIO()
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setattr(sys, "argv", ["capture", "0"])
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=output))
    monkeypatch.setattr(time, "monotonic", lambda: elapsed[0])
    if fails_after_startup:
        with pytest.raises(RuntimeError, match="frame"):
            exec(CAPTURE, {})
        assert output.getvalue() == b""
    else:
        exec(CAPTURE, {})
        assert output.getvalue() == b"\xff\xd8exposed"
    assert released == [True]
