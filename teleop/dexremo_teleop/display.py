"""Live camera and data view in Rerun (needs `pip install rerun-sdk`; LeRobot installs it).

A background thread sends the newest camera frames (JPEG-compressed), the hand's
joint angles and the fingertip forces to the Rerun viewer at a modest rate. It
only reads the latest values, so it never holds up the control loop or the
recording.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from .force import FINGERTIPS
from .joints import JOINT_NAMES


class RerunDisplay:
    def __init__(self, cameras: dict, loop, reader=None, rate: float = 10.0, session: str = "dexremo"):
        try:
            import rerun as rr
        except ImportError as e:
            raise ImportError("--display needs Rerun: pip install rerun-sdk") from e
        self.rr = rr
        self.cameras, self.loop, self.reader, self.rate = cameras, loop, reader, rate
        # The viewer is a separate program installed next to Python; find it even if
        # the environment is not activated (PATH not set).
        import os
        import shutil
        import sys

        bin_dir = os.path.dirname(sys.executable)
        if shutil.which("rerun") is None and os.path.exists(os.path.join(bin_dir, "rerun")):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        if shutil.which("rerun") is None:
            raise RuntimeError("--display needs the Rerun viewer: pip install rerun-sdk")
        rr.init(session)
        rr.spawn(memory_limit="10%")
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._scalar = getattr(rr, "Scalars", None) or rr.Scalar  # renamed in Rerun 0.23

    def start(self) -> RerunDisplay:
        self._thread.start()
        return self

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _set_time(self, t: float) -> None:
        rr = self.rr
        if hasattr(rr, "set_time"):
            rr.set_time("time", duration=t)
        else:
            rr.set_time_seconds("time", t)

    def _run(self) -> None:
        rr = self.rr
        t0 = time.perf_counter()
        period = 1.0 / self.rate
        while not self._stop.is_set():
            tick = time.perf_counter()
            try:
                self._set_time(tick - t0)
                for name, cam in self.cameras.items():
                    frame, age = cam.latest()
                    if frame is not None and age < 1.0:
                        rr.log(f"camera_{name}", rr.Image(frame).compress(jpeg_quality=80))  # one view per camera
                snap = self.loop.latest()
                if snap is not None:
                    q = np.degrees(snap.q_command)
                    for name, v in zip(JOINT_NAMES, q):
                        rr.log(f"joints_deg/{name}", self._scalar(float(v)))
                if self.reader is not None:
                    forces, age = self.reader.latest()
                    if forces is not None and age < 0.5:
                        for f in FINGERTIPS:
                            for axis, v in zip("xyz", forces[f]):
                                rr.log(f"force_sensor_N/{f}/{axis}", self._scalar(float(v)))
            except Exception:
                pass  # the viewer was closed or is busy: keep going, it is only a display
            time.sleep(max(0.0, period - (time.perf_counter() - tick)))
