"""The DexRemo hand (follower) or leader device on one servo bus.

Joint angles are in radians and use the simulation model's convention:
q = 0 is the zero pose, and the sign of each joint matches ``sim/README.md``.

Calibration stores the zero pose in each servo (``Homing_Offset``), so that the
zero pose reads 2048 ticks, and saves each joint's range of motion and sign to a
JSON file.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .joints import JOINT_NAMES, SERVO_IDS
from .servo_bus import CENTER, RESOLUTION, ServoBus, ServoError, decode_offset, encode_offset

CALIBRATION_DIR = Path.home() / ".dexremo" / "calibration"
TICKS_PER_RAD = RESOLUTION / (2 * math.pi)

# Follower position-loop settings: a lower P gain than the factory default (32)
# avoids shaking; these are the values used in the paper's experiments.
FOLLOWER_SETTINGS = {
    "Return_Delay_Time": 0,
    "Operating_Mode": 0,  # position mode
    "P_Coefficient": 10,
    "I_Coefficient": 0,
    "D_Coefficient": 20,
    "Acceleration": 254,
    "Torque_Limit": 1000,
}


@dataclass
class JointCalibration:
    id: int
    homing_offset: int  # ticks, as written to the servo
    range_min: int  # ticks, after the offset
    range_max: int
    sign: int  # +1 or -1, see joints.DEFAULT_SIGNS


def calibration_path(name: str) -> Path:
    path = Path(name)
    if path.suffix == ".json" or path.parent != Path("."):
        return path
    return CALIBRATION_DIR / f"{name}.json"


def save_calibration(calib: dict[str, JointCalibration], name: str) -> Path:
    path = calibration_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({k: asdict(v) for k, v in calib.items()}, indent=2) + "\n")
    return path


def load_calibration(name: str) -> dict[str, JointCalibration]:
    path = calibration_path(name)
    if not path.exists():
        raise FileNotFoundError(
            f"No calibration file at {path}. Run `dexremo-teleop calibrate --name {name} ...` first."
        )
    data = json.loads(path.read_text())
    missing = set(JOINT_NAMES) - set(data)
    if missing:
        raise ValueError(f"{path} has no entry for {sorted(missing)}")
    return {name: JointCalibration(**data[name]) for name in JOINT_NAMES}


class Hand:
    """Twelve servos on one port, read and written as joint angles."""

    def __init__(self, port: str, calibration: dict[str, JointCalibration] | None = None, **bus_kwargs):
        self.bus = ServoBus(port, **bus_kwargs)
        self.calibration = calibration
        self.ids = [SERVO_IDS[n] for n in JOINT_NAMES]

    # -- connection -------------------------------------------------------------

    def connect(self) -> None:
        self.bus.open()
        missing = [i for i in self.ids if self.bus.ping(i) is None]
        if missing:
            self.bus.close()
            raise ServoError(
                f"No answer on {self.bus.port} from servo IDs {missing}. "
                "Check power, cables and IDs (`dexremo-teleop scan`)."
            )
        if self.calibration is not None:
            self._check_offsets()

    def disconnect(self, disable_torque: bool = True) -> None:
        if disable_torque:
            try:
                self.bus.set_torque(self.ids, False)
            except ServoError:
                pass
        self.bus.close()

    def _check_offsets(self) -> None:
        wrong = []
        for name, cal in self.calibration.items():
            stored = decode_offset(self.bus.read(cal.id, "Homing_Offset"))
            if stored != cal.homing_offset:
                wrong.append(name)
        if wrong:
            raise ServoError(
                f"The zero offsets in servos {wrong} on {self.bus.port} do not match the calibration "
                "file. The servos were calibrated elsewhere or replaced: run `dexremo-teleop calibrate` again."
            )

    # -- conversion -------------------------------------------------------------

    def _arrays(self):
        cal = [self.calibration[n] for n in JOINT_NAMES]
        sign = np.array([c.sign for c in cal], dtype=float)
        lo = np.array([c.range_min for c in cal], dtype=float)
        hi = np.array([c.range_max for c in cal], dtype=float)
        return sign, lo, hi

    def ticks_to_q(self, ticks: np.ndarray) -> np.ndarray:
        sign, _, _ = self._arrays()
        return sign * (np.asarray(ticks, dtype=float) - CENTER) / TICKS_PER_RAD

    def q_to_ticks(self, q: np.ndarray, margin: int = 0) -> np.ndarray:
        """Convert to ticks and clip to the calibrated range (minus a safety margin)."""
        sign, lo, hi = self._arrays()
        ticks = CENTER + sign * np.asarray(q, dtype=float) * TICKS_PER_RAD
        return np.clip(np.round(ticks), lo + margin, hi - margin).astype(int)

    # -- I/O ----------------------------------------------------------------------

    def read_raw_ticks(self) -> np.ndarray:
        """Present_Position as the servos report it, without wrapping to one turn.

        Some servos count whole turns and report values outside 0-4095 (bit 15 is the
        sign). Each joint moves less than one turn, so read_ticks() wraps them back.
        """
        values = self.bus.sync_read("Present_Position", self.ids)
        raw = np.array([values[i] for i in self.ids])
        return np.where(raw & 0x8000, -(raw & 0x7FFF), raw)

    def read_ticks(self) -> np.ndarray:
        """Present_Position wrapped to one turn, 0-4095."""
        return self.read_raw_ticks() % RESOLUTION

    def multi_turn_joints(self) -> list[str]:
        """Joints whose servo reports a position outside one turn."""
        raw = self.read_raw_ticks()
        return [n for n, r in zip(JOINT_NAMES, raw) if not 0 <= r < RESOLUTION]

    def read_q(self) -> np.ndarray:
        """Joint angles in radians, ordered as joints.JOINT_NAMES."""
        return self.ticks_to_q(self.read_ticks())

    def read_current(self) -> np.ndarray:
        """Servo currents in raw units (6.5 mA per unit on the ST-3215)."""
        values = self.bus.sync_read("Present_Current", self.ids)
        return np.array([values[i] for i in self.ids])

    def write_q(self, q: np.ndarray, margin: int = 0) -> np.ndarray:
        """Command joint angles (radians). Returns the angles actually sent after clipping."""
        ticks = self.q_to_ticks(q, margin)
        self.bus.sync_write("Goal_Position", dict(zip(self.ids, ticks)))
        return self.ticks_to_q(ticks)

    def set_torque(self, enabled: bool) -> None:
        if enabled:
            # A servo that counts whole turns would try to unwind them to reach a
            # goal inside 0-4095. Do not drive it.
            multi = self.multi_turn_joints()
            if multi:
                raise ServoError(
                    f"Servos {multi} on {self.bus.port} report a position outside one turn. "
                    "Power-cycle the hand and run `dexremo-teleop scan`; calibrate again if it persists."
                )
            # Hold the current pose so the hand does not jump when torque comes on.
            self.bus.sync_write("Goal_Position", dict(zip(self.ids, self.read_ticks())))
        self.bus.set_torque(self.ids, enabled)

    def configure_follower(self) -> None:
        self.bus.set_torque(self.ids, False)
        for i in self.ids:
            for reg, value in FOLLOWER_SETTINGS.items():
                self.bus.write_if_changed(i, reg, value)

    def configure_leader(self) -> None:
        self.bus.set_torque(self.ids, False)
        for i in self.ids:
            self.bus.write_if_changed(i, "Return_Delay_Time", 0)

    # -- calibration --------------------------------------------------------------

    def reset_offsets_and_limits(self) -> None:
        """Clear zero offsets and position limits left by an earlier calibration."""
        self.bus.set_torque(self.ids, False)
        for i in self.ids:
            self.bus.write_eeprom(i, "Homing_Offset", 0)
            self.bus.write_eeprom(i, "Min_Position_Limit", 0)
            self.bus.write_eeprom(i, "Max_Position_Limit", RESOLUTION - 1)

    def set_zero_here(self, samples: int = 10) -> dict[str, int]:
        """Store the current pose as the zero pose. Call reset_offsets_and_limits() first."""
        readings = np.array([self.read_ticks() for _ in range(samples)])
        # Average relative to the first sample, so readings that straddle 0/4095 do not
        # average to the opposite side of the turn.
        first = readings[0]
        delta = (readings - first + RESOLUTION // 2) % RESOLUTION - RESOLUTION // 2
        raw = np.round(first + delta.mean(axis=0)).astype(int) % RESOLUTION
        offsets = {}
        for name, i, r in zip(JOINT_NAMES, self.ids, raw):
            # Present_Position = raw position - Homing_Offset
            offset = int(r) - CENTER
            self.bus.write_eeprom(i, "Homing_Offset", encode_offset(offset))
            offsets[name] = decode_offset(encode_offset(offset))
        time.sleep(0.05)
        return offsets
