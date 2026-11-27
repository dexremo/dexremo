"""Template: read your own load-cell transmitter.

Copy this file, fill in read_channels() from your transmitter's datasheet, then run

    dexremo-teleop force-zero --force my_transmitter.py:MyTransmitter      # once a day, after power-on
    dexremo-teleop force-check --force my_transmitter.py:MyTransmitter
    dexremo-teleop teleop ... --force my_transmitter.py:MyTransmitter --force-calibration my_force_calib.json

Most RS485 load-cell transmitters speak Modbus RTU. The datasheet gives the slave
address, the baud rate, the register that holds the first channel, the data
format of each channel (for example a 32-bit signed integer, big endian, with a
fixed number of decimals) and the zeroing command. An AI coding assistant can
write read_channels() for you if you give it the datasheet.

Wire the load cells to channels 1-9 in the order of CHANNELS
(see hardware/force_calibration.md, step 1).
"""

import numpy as np
import serial  # pip install pyserial

from dexremo_teleop.force import CHANNELS, TransmitterForceSensor


class MyTransmitter(TransmitterForceSensor):
    PORT = "/dev/ttyUSB0"  # the RS485-USB adapter
    BAUDRATE = 115200  # from the datasheet

    def connect(self) -> None:
        self.serial = serial.Serial(self.PORT, self.BAUDRATE, timeout=0.1)

    def read_channels(self) -> np.ndarray:
        # TODO: send the datasheet's "read all channels" request, read the reply,
        # check its length (and CRC), and decode one value per channel.
        # Return the values in the order of CHANNELS, scaled to about newtons.
        raise NotImplementedError("Fill in read_channels() for your transmitter.")
        return np.zeros(len(CHANNELS))

    def zero(self) -> None:
        # TODO: send the datasheet's zeroing command (often a Modbus "write single
        # coil" or "write register" request) and check the reply. Called by
        # `dexremo-teleop force-zero`, once a day after power-on.
        raise NotImplementedError("Fill in zero() for your transmitter.")

    def close(self) -> None:
        self.serial.close()
