"""Killable OpenCV capture workers bound permission and device-read stalls."""

import base64
import subprocess
import sys
import threading

CAPTURE = """
import sys, time, cv2
cap=cv2.VideoCapture(int(sys.argv[1]))
try:
 if not cap.isOpened(): raise RuntimeError('Camera unavailable or permission denied')
 cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
 cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
 # USB cameras can return valid but black frames while auto-exposure starts.
 # Drain startup frames instead of sleeping with a stale frame in the buffer.
 started=time.monotonic()
 while True:
  ok,frame=cap.read()
  if not ok: raise RuntimeError('Camera did not return a frame')
  if time.monotonic()-started >= 0.7: break
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

    def snapshot(self, index):
        try:
            image = base64.b64encode(self.frame(index)).decode("ascii")
            return dict(
                index=index,
                available=True,
                image="data:image/jpeg;base64," + image,
                error=None,
            )
        except (ValueError, OSError) as exc:
            return dict(index=index, available=False, image=None, error=str(exc))

    def scan(self, max_index=4):
        if not isinstance(max_index, int) or not 0 <= max_index <= 7:
            raise ValueError("Maximum camera index must be 0–7")
        return [self.snapshot(index) for index in range(max_index + 1)]

    def shutdown(self):
        self.closed = True
