"""Minimal driver for Feetech STS-series serial bus servos (ST-3215).

Built on the official Feetech Python SDK (``pip install feetech-servo-sdk``,
imported as ``scservo_sdk``). Only the registers this project needs are listed.
"""

from __future__ import annotations

import time

import scservo_sdk as scs

DEFAULT_BAUDRATE = 1_000_000
RESOLUTION = 4096  # encoder ticks per turn
CENTER = 2048  # position the zero pose is mapped to

# Register map: name -> (address, size in bytes). Addresses up to 39 are EEPROM.
REG = {
    "Model_Number": (3, 2),
    "ID": (5, 1),
    "Baud_Rate": (6, 1),
    "Return_Delay_Time": (7, 1),
    "Min_Position_Limit": (9, 2),
    "Max_Position_Limit": (11, 2),
    "P_Coefficient": (21, 1),
    "D_Coefficient": (22, 1),
    "I_Coefficient": (23, 1),
    "Homing_Offset": (31, 2),
    "Operating_Mode": (33, 1),
    "Torque_Enable": (40, 1),
    "Acceleration": (41, 1),
    "Goal_Position": (42, 2),
    "Torque_Limit": (48, 2),
    "Lock": (55, 1),
    "Present_Position": (56, 2),
    "Present_Load": (60, 2),
    "Present_Voltage": (62, 1),
    "Present_Temperature": (63, 1),
    "Present_Current": (69, 2),
}

# Homing_Offset is stored as sign-magnitude with the sign in bit 11.
_OFFSET_SIGN_BIT = 11
MAX_HOMING_OFFSET = (1 << _OFFSET_SIGN_BIT) - 1


class ServoError(RuntimeError):
    pass


def encode_offset(value: int) -> int:
    value = max(-MAX_HOMING_OFFSET, min(MAX_HOMING_OFFSET, int(value)))
    return (1 << _OFFSET_SIGN_BIT) | -value if value < 0 else value


def decode_offset(raw: int) -> int:
    magnitude = raw & MAX_HOMING_OFFSET
    return -magnitude if raw >> _OFFSET_SIGN_BIT & 1 else magnitude


class _PortHandler(scs.PortHandler):
    # The SDK's default packet timeout is too short for a 12-servo sync read and
    # causes sporadic timeouts. Use a fixed 50 ms margin instead.
    def setPacketTimeout(self, packet_length):  # noqa: N802
        self.packet_start_time = self.getCurrentTime()
        self.packet_timeout = self.tx_time_per_byte * (packet_length + 3) + 50


class ServoBus:
    """One serial port with one or more servos on it."""

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE, retries: int = 3):
        self.port = port
        self.baudrate = baudrate
        self.retries = retries
        self._port: _PortHandler | None = None
        self._packet = scs.PacketHandler(0)  # STS servos: protocol 0, little endian

    # -- connection -------------------------------------------------------------

    def open(self) -> ServoBus:
        port = _PortHandler(self.port)
        try:
            ok = port.openPort()
        except Exception as e:  # serial.SerialException, PermissionError, ...
            raise ServoError(f"Cannot open {self.port}: {e}") from e
        if not ok or not port.setBaudRate(self.baudrate):
            raise ServoError(f"Cannot open {self.port} at {self.baudrate} baud.")
        self._port = port
        return self

    def close(self) -> None:
        if self._port is not None:
            self._port.closePort()
            self._port = None

    def __enter__(self) -> ServoBus:
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def _ph(self) -> _PortHandler:
        if self._port is None:
            raise ServoError(f"{self.port} is not open.")
        return self._port

    def _fail(self, comm: int, what: str) -> ServoError:
        return ServoError(f"{what}: {self._packet.getTxRxResult(comm)}")

    # -- single servo -----------------------------------------------------------

    def ping(self, servo_id: int) -> int | None:
        """Return the model number, or None if no servo answers."""
        model, comm, _ = self._packet.ping(self._ph, servo_id)
        return model if comm == scs.COMM_SUCCESS else None

    def scan(self, ids=range(0, 254)) -> dict[int, int]:
        return {i: m for i in ids if (m := self.ping(i)) is not None}

    def read(self, servo_id: int, reg: str) -> int:
        addr, size = REG[reg]
        fn = {1: self._packet.read1ByteTxRx, 2: self._packet.read2ByteTxRx}[size]
        for _ in range(self.retries + 1):
            value, comm, _error = fn(self._ph, servo_id, addr)
            if comm == scs.COMM_SUCCESS:
                return value
            time.sleep(0.01)
        raise self._fail(comm, f"Read {reg} from servo {servo_id}")

    def write(self, servo_id: int, reg: str, value: int) -> None:
        addr, size = REG[reg]
        fn = {1: self._packet.write1ByteTxRx, 2: self._packet.write2ByteTxRx}[size]
        for _ in range(self.retries + 1):
            comm, _error = fn(self._ph, servo_id, addr, int(value))
            if comm == scs.COMM_SUCCESS:
                return
            time.sleep(0.01)
        raise self._fail(comm, f"Write {reg}={value} to servo {servo_id}")

    def write_if_changed(self, servo_id: int, reg: str, value: int) -> bool:
        """Write only if the value differs. Saves flash wear on EEPROM registers."""
        if self.read(servo_id, reg) == value:
            return False
        self.write(servo_id, reg, value)
        return True

    def write_eeprom(self, servo_id: int, reg: str, value: int) -> None:
        """Write a value that must survive a power cycle (ID, offsets, limits)."""
        if self.read(servo_id, reg) == value:
            return
        self.write(servo_id, "Lock", 0)
        try:
            self.write(servo_id, reg, value)
        finally:
            self.write(servo_id, "Lock", 1)

    # -- several servos at once -------------------------------------------------

    def sync_read(self, reg: str, ids: list[int]) -> dict[int, int]:
        addr, size = REG[reg]
        group = scs.GroupSyncRead(self._ph, self._packet, addr, size)
        for i in ids:
            group.addParam(i)
        for _ in range(self.retries + 1):
            comm = group.txRxPacket()
            if comm == scs.COMM_SUCCESS:
                break
            time.sleep(0.005)
        else:
            raise self._fail(comm, f"Sync read {reg} from {ids}")
        missing = [i for i in ids if not group.isAvailable(i, addr, size)]
        if missing:
            raise ServoError(f"Sync read {reg}: no data from servos {missing}")
        return {i: group.getData(i, addr, size) for i in ids}

    def sync_write(self, reg: str, values: dict[int, int]) -> None:
        addr, size = REG[reg]
        group = scs.GroupSyncWrite(self._ph, self._packet, addr, size)
        for i, v in values.items():
            v = int(v)
            data = [v & 0xFF] if size == 1 else [v & 0xFF, (v >> 8) & 0xFF]
            group.addParam(i, data)
        comm = group.txPacket()
        if comm != scs.COMM_SUCCESS:
            raise self._fail(comm, f"Sync write {reg}")

    def set_torque(self, ids: list[int], enabled: bool) -> None:
        for i in ids:
            self.write(i, "Torque_Enable", 1 if enabled else 0)
