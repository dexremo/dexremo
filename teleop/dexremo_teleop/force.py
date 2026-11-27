"""Fingertip force-sensor interface.

The teleoperation code does not depend on any particular transmitter. It asks a
``ForceSensor`` for one 3-axis force per fingertip, in newtons, in the fingertip's
sensor frame (``hardware/force_calibration.md#sensor-frame-and-load-cell-names``).

* ``NoForceSensor`` is the default: the hand has no force-sensing fingertips.
* ``TransmitterForceSensor`` is the base class for a real transmitter. Subclass it,
  implement ``read_channels()`` from your transmitter's datasheet, and pass the
  file to the teleoperation script with ``--force path/to/file.py:ClassName``.
  See ``examples/my_transmitter.py``.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

# Fingertip numbers follow the servo IDs: 1 = right, 2 = mid, 3 = left.
FINGERTIPS = ("right", "mid", "left")

# Transmitter channels 1-9, in this order (see force_calibration.md, step 1).
CHANNELS = ("1+X", "1+Y", "1-Y", "2+X", "2+Y", "2-Y", "3+X", "3+Y", "3-Y")


class ForceSensor(ABC):
    """Gives one force vector per fingertip."""

    def connect(self) -> None:
        pass

    @abstractmethod
    def read(self) -> dict[str, np.ndarray] | None:
        """Return {"right": F, "mid": F, "left": F}, each F = (Fx, Fy, Fz) in newtons in
        the sensor frame, or None if this hand has no force sensors."""

    def close(self) -> None:
        pass


class NoForceSensor(ForceSensor):
    """For a hand without force-sensing fingertips."""

    def read(self) -> None:
        return None


class TransmitterForceSensor(ForceSensor):
    """Base class for a load-cell transmitter with nine channels.

    Subclasses implement ``read_channels()``. This class applies the per-fingertip
    linear map from step 6 of the calibration method, F = K @ r + c.

    The calibration file is JSON with one entry per fingertip:

        {"right": {"K": [[...], [...], [...]], "c": [0, 0, 0]}, "mid": {...}, "left": {...}}

    Without a file, K is the identity and c is zero, so the readings pass through
    with only the channel-to-axis mapping (A=+X, B=+Y, C=-Y, see below).
    """

    def __init__(self, calibration: str | Path | None = None):
        self.K = {f: _UNCALIBRATED_K.copy() for f in FINGERTIPS}
        self.c = {f: np.zeros(3) for f in FINGERTIPS}
        if calibration:
            data = json.loads(Path(calibration).read_text())
            for f in FINGERTIPS:
                if f in data:
                    self.K[f] = np.asarray(data[f]["K"], dtype=float).reshape(3, 3)
                    self.c[f] = np.asarray(data[f].get("c", [0, 0, 0]), dtype=float).reshape(3)

    @abstractmethod
    def read_channels(self) -> np.ndarray:
        """Return the nine channel readings as an array of shape (9,), in the order of
        CHANNELS, scaled roughly to newtons (step 3 of the calibration method)."""

    def read(self) -> dict[str, np.ndarray]:
        r = np.asarray(self.read_channels(), dtype=float).reshape(3, 3)
        return {f: self.K[f] @ r[i] + self.c[f] for i, f in enumerate(FINGERTIPS)}


# Rough map from (A, B, C) = (+X cell, +Y cell, -Y cell) readings to (Fx, Fy, Fz),
# from the sensor geometry alone. Use it only until the fingertip is calibrated.
_UNCALIBRATED_K = np.array(
    [
        [1.0, -0.5, -0.5],
        [0.0, np.sqrt(3) / 2, -np.sqrt(3) / 2],
        [1.0, 1.0, 1.0],
    ]
)


def load_force_sensor(spec: str | None, calibration: str | None = None) -> ForceSensor:
    """Create a force sensor from a command-line spec.

    ``none`` (or empty) gives NoForceSensor. ``path/to/file.py:ClassName`` or
    ``package.module:ClassName`` loads your own ForceSensor subclass; it is built
    with ``calibration=<file>`` if it is a TransmitterForceSensor.
    """
    if not spec or spec.lower() == "none":
        return NoForceSensor()
    if ":" not in spec:
        raise ValueError(f"--force expects 'none' or 'file.py:ClassName', got {spec!r}")
    target, class_name = spec.rsplit(":", 1)
    if target.endswith(".py"):
        module_spec = importlib.util.spec_from_file_location(Path(target).stem, target)
        if module_spec is None or module_spec.loader is None:
            raise ImportError(f"Cannot load {target}")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
        module = importlib.import_module(target)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, ForceSensor)):
        raise TypeError(f"{spec} is not a ForceSensor subclass")
    if issubclass(cls, TransmitterForceSensor):
        return cls(calibration=calibration)
    return cls()
