"""Forward kinematics from the simulation model (needs `pip install mujoco`).

Gives each fingertip's pose and turns fingertip forces from the sensor frame into
the wrist frame (the hand's base frame, on the flange face):

    F_wrist = R(q) @ F_sensor

with R(q) the orientation of ``{finger}_force_site`` in ``base_link``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .force import FINGERTIPS
from .joints import JOINT_NAMES

# The model files live in sim/ of the same repository.
SIM_DIR = Path(__file__).resolve().parents[2] / "sim" / "mjcf"
DEFAULT_MODEL = SIM_DIR / "dexremo_hand.xml"
DEFAULT_SCENE = SIM_DIR / "scene.xml"  # the hand hanging palm down, for display


def _require_mujoco():
    try:
        import mujoco
    except ImportError as e:
        raise ImportError("This feature needs MuJoCo: pip install mujoco") from e
    return mujoco


class HandKinematics:
    def __init__(self, model_path: str | Path = DEFAULT_MODEL):
        mujoco = _require_mujoco()
        self._mj = mujoco
        self.model = mujoco.MjModel.from_xml_path(str(model_path))
        self.data = mujoco.MjData(self.model)
        self.qadr = np.array([self.model.joint(n).qposadr[0] for n in JOINT_NAMES])
        self.base = self.model.body("base_link").id
        names = {self.model.site(i).name for i in range(self.model.nsite)}
        self.has_sensors = all(f"{f}_force_site" in names for f in FINGERTIPS)
        self.sites = {
            f: self.model.site(f"{f}_force_site" if self.has_sensors else f"{f}_tip_site").id for f in FINGERTIPS
        }
        self.tips = {f: self.model.site(f"{f}_tip_site").id for f in FINGERTIPS}

    def update(self, q: np.ndarray) -> None:
        """Set the joint angles (radians, ordered as JOINT_NAMES) and recompute poses."""
        self.data.qpos[self.qadr] = q
        self._mj.mj_kinematics(self.model, self.data)

    def _base_pose(self):
        return self.data.xpos[self.base], self.data.xmat[self.base].reshape(3, 3)

    def sensor_pose(self, finger: str) -> tuple[np.ndarray, np.ndarray]:
        """Position (m) and rotation of the fingertip sensor frame in the wrist frame."""
        p0, r0 = self._base_pose()
        s = self.sites[finger]
        p = self.data.site_xpos[s]
        r = self.data.site_xmat[s].reshape(3, 3)
        return r0.T @ (p - p0), r0.T @ r

    def tip_pose(self, finger: str) -> np.ndarray:
        """Fingertip pose in the wrist frame: (x, y, z, qx, qy, qz, qw), metres.

        The position is the fingertip point (``{finger}_tip_site``); the orientation
        is that of the fingertip sensor frame (``{finger}_force_site``) if the model
        has one, otherwise that of the fingertip site.
        """
        p0, r0 = self._base_pose()
        pos = r0.T @ (self.data.site_xpos[self.tips[finger]] - p0)
        rot = r0.T @ self.data.site_xmat[self.sites[finger]].reshape(3, 3)
        wxyz = np.zeros(4)
        self._mj.mju_mat2Quat(wxyz, rot.flatten())
        if wxyz[0] < 0:  # keep qw >= 0 so the same orientation always gives the same numbers
            wxyz = -wxyz
        return np.concatenate([pos, wxyz[1:], wxyz[:1]])

    def forces_to_wrist(self, forces: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Sensor-frame forces -> wrist-frame forces, at the pose of the last update()."""
        if not self.has_sensors:
            raise ValueError("This model has no fingertip force sensors; use dexremo_hand.xml.")
        return {f: self.sensor_pose(f)[1] @ np.asarray(forces[f], dtype=float) for f in FINGERTIPS}
