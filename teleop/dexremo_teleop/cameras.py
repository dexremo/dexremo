"""USB cameras, each read in its own thread (needs `pip install opencv-python`).

The thread keeps only the newest frame, so the recorder always gets a fresh image
and a slow camera never holds up the control loop.
"""

from __future__ import annotations

import threading
import time

import numpy as np


def parse_camera_spec(spec: str) -> tuple[str, str | int]:
    """'wrist=/dev/video4' or 'wrist=4' -> ('wrist', '/dev/video4' or 4)."""
    if "=" not in spec:
        raise ValueError(f"--camera expects name=device, e.g. wrist=/dev/video4, got {spec!r}")
    name, dev = spec.split("=", 1)
    if not name.isidentifier():
        raise ValueError(f"Camera name {name!r} must be a plain word, e.g. left, right, wrist")
    return name, int(dev) if dev.isdigit() else dev


class Camera:
    def __init__(self, name: str, device: str | int, width: int = 640, height: int = 480, fps: int = 30,
                 fourcc: str = "MJPG"):
        import cv2

        self._cv2 = cv2
        self.name, self.device = name, device
        self.width, self.height = width, height
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2) if isinstance(device, str) else cv2.VideoCapture(device)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {name} ({device}).")
        # MJPG keeps USB bandwidth low; several YUYV cameras on one USB 2 bus do not fit.
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._stamp = 0.0
        self.count = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            if frame.shape[:2] != (self.height, self.width):
                frame = self._cv2.resize(frame, (self.width, self.height))
            rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
            with self._lock:
                self._frame, self._stamp = rgb, time.perf_counter()
                self.count += 1

    def latest(self) -> tuple[np.ndarray | None, float]:
        """Newest frame (H x W x 3, RGB, uint8) and its age in seconds."""
        with self._lock:
            return self._frame, time.perf_counter() - self._stamp

    def wait_first_frame(self, timeout: float = 5.0) -> None:
        t0 = time.perf_counter()
        while self.latest()[0] is None:
            if time.perf_counter() - t0 > timeout:
                raise RuntimeError(f"Camera {self.name} ({self.device}) gives no frames.")
            time.sleep(0.02)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        self.cap.release()
