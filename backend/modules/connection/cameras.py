"""Killable OpenCV capture workers bound permission and device-read stalls."""

import subprocess
import sys
import threading

CAPTURE = """
import sys, cv2
cap=cv2.VideoCapture(int(sys.argv[1]))
try:
 if not cap.isOpened(): raise RuntimeError('Camera unavailable or permission denied')
 cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
 cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
 ok,frame=cap.read()
 if not ok: raise RuntimeError('Camera did not return a frame')
 ok,jpeg=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,75])
 if not ok: raise RuntimeError('JPEG encoding failed')
 sys.stdout.buffer.write(jpeg.tobytes())
finally: cap.release()
"""


class CameraService:
    def __init__(self, timeout=4, runner=subprocess.run):
        self.timeout = timeout
        self.runner = runner
        self.lock = threading.Lock()
        self.closed = False

    def frame(self, index):
        if not isinstance(index, int) or not 0 <= index <= 7:
            raise ValueError("Camera index must be 0–7")
        if not self.lock.acquire(timeout=0.1):
            raise ValueError("Camera is busy; wait for current capture or scan")
        try:
            if self.closed:
                raise ValueError("Camera service closed")
            try:
                result = self.runner(
                    [sys.executable, "-c", CAPTURE, str(index)],
                    capture_output=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError(
                    "Camera timed out; check camera permission or device availability"
                ) from exc
            if result.returncode or not result.stdout.startswith(b"\xff\xd8"):
                raise ValueError(
                    "Camera unavailable or permission denied: "
                    + result.stderr.decode(errors="replace")[-400:]
                )
            if len(result.stdout) > 8_000_000:
                raise ValueError("Camera frame exceeds local size limit")
            return result.stdout
        finally:
            self.lock.release()

    def scan(self, max_index=4):
        rows = []
        for index in range(max_index + 1):
            try:
                self.frame(index)
                rows.append(dict(index=index, available=True, error=None))
            except ValueError as exc:
                rows.append(dict(index=index, available=False, error=str(exc)))
        return rows

    def shutdown(self):
        self.closed = True
