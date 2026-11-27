"""Live 3D view of the hand with fingertip force arrows (needs `pip install mujoco`).

The control loop only hands over the latest joint angles and forces
(``update()``, a copy under a lock). Forward kinematics, arrows and rendering run
in their own threads, so a slow screen does not slow down teleoperation.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

from .force import FINGERTIPS
from .kinematics import DEFAULT_SCENE, HandKinematics

ARROW_M_PER_N = 0.025  # arrow length: 2.5 cm per newton
ARROW_MAX_M = 0.15
ARROW_WIDTH_M = 0.008
ARROW_RGBA = {"right": (0.95, 0.25, 0.2, 1), "mid": (0.2, 0.75, 0.3, 1), "left": (0.2, 0.45, 0.95, 1)}
HAND_RGBA = (0.74, 0.76, 0.8, 1)


class HandViewer:
    def __init__(self, scene: str | Path = DEFAULT_SCENE, rate: float = 30.0):
        self.kin = HandKinematics(scene)
        m = self.kin.model
        # Light grey hand, so that the coloured force arrows stand out.
        for g in range(m.ngeom):
            if m.geom_group[g] == 2 and m.geom_bodyid[g] != 0:
                m.geom_rgba[g] = HAND_RGBA
                m.geom_matid[g] = -1
        m.vis.headlight.ambient[:] = 0.45
        m.vis.headlight.diffuse[:] = 0.65
        self.rate = rate
        self._lock = threading.Lock()
        self._q = np.zeros(12)
        self._forces: dict[str, np.ndarray] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.handle = None

    def start(self) -> None:
        import mujoco.viewer

        m, d = self.kin.model, self.kin.data
        self.handle = mujoco.viewer.launch_passive(m, d, show_left_ui=False, show_right_ui=False)
        with self.handle.lock():
            self.handle.opt.geomgroup[3] = 0  # hide collision hulls
            cam = self.handle.cam
            cam.lookat[:] = (0.0, 0.0, 0.30)
            cam.distance, cam.azimuth, cam.elevation = 0.7, 150, -20
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def update(self, q: np.ndarray, forces: dict[str, np.ndarray] | None = None) -> None:
        """Hand over the latest joint angles (radians) and sensor-frame forces. Cheap."""
        with self._lock:
            self._q = np.array(q, dtype=float)
            self._forces = None if forces is None else {f: np.array(v, dtype=float) for f, v in forces.items()}

    @property
    def is_running(self) -> bool:
        return self.handle is not None and self.handle.is_running()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self.handle is not None:
            self.handle.close()
            # Let the viewer's render thread finish before Python exits; quitting
            # while it is still shutting down crashes the process (free(): invalid size).
            deadline = time.perf_counter() + 2.0
            while self.handle.is_running() and time.perf_counter() < deadline:
                time.sleep(0.02)
            time.sleep(0.3)

    def _run(self) -> None:
        import mujoco

        period = 1.0 / self.rate
        while not self._stop.is_set() and self.handle.is_running():
            t0 = time.perf_counter()
            with self._lock:
                q, forces = self._q, self._forces
            with self.handle.lock():
                self.kin.update(q)
                scn = self.handle.user_scn
                scn.ngeom = 0
                if forces is not None and self.kin.has_sensors:
                    for f in FINGERTIPS:
                        s = self.kin.sites[f]
                        p = self.kin.data.site_xpos[self.kin.tips[f]]  # draw from the fingertip point
                        fw = self.kin.data.site_xmat[s].reshape(3, 3) @ forces[f]  # world frame
                        n = np.linalg.norm(fw)
                        if n < 0.05 or scn.ngeom >= scn.maxgeom:
                            continue
                        length = min(n * ARROW_M_PER_N, ARROW_MAX_M)
                        g = scn.geoms[scn.ngeom]
                        mujoco.mjv_initGeom(g, mujoco.mjtGeom.mjGEOM_ARROW, np.zeros(3), np.zeros(3),
                                            np.zeros(9), np.array(ARROW_RGBA[f], dtype=np.float32))
                        mujoco.mjv_connector(g, mujoco.mjtGeom.mjGEOM_ARROW, ARROW_WIDTH_M, p, p + fw / n * length)
                        scn.ngeom += 1
            self.handle.sync()
            time.sleep(max(0.0, period - (time.perf_counter() - t0)))
