# DexRemo teleoperation

**English** | [中文](README_zh.md)

Python tools for the DexRemo hand and its leader device: servo ID setup, zero-pose calibration, joint read and write, and leader–follower teleoperation. Force sensing is optional: the code runs without force sensors and has an interface for your own transmitter.

Joint names, zero pose and signs are the same as in the [simulation model](../sim/README.md#joints). Joint angles are in radians.

## Install

Python 3.10 or later.

```bash
cd teleop
pip install -e .
```

This installs the `dexremo-teleop` command. It needs only `numpy`, `pyserial` and the Feetech servo SDK (`feetech-servo-sdk`).

For the live 3D view (`--viewer`, `view`) and wrist-frame forces, also install MuJoCo:

```bash
pip install -e ".[viewer]"
```

**Linux:** your user needs access to the serial ports. Run this once, then log out and in again:

```bash
sudo usermod -aG dialout $USER
```

## 1. Find the ports

Connect the hand's servo driver board and the leader's board over USB, then run:

```bash
dexremo-teleop ports
```

Unplug one board and run it again to see which port belongs to which device. Below, the hand is on `/dev/ttyACM0` and the leader on `/dev/ttyACM1`; replace these with your own ports.

## 2. Set the servo IDs

New servos all have ID 1. Give each servo its ID from the [servo ID map](../hardware/assembly/README.md#servo-id-map) before you build it in. Connect **one servo at a time** to the driver board:

```bash
dexremo-teleop set-id --port /dev/ttyACM0 --id 5
```

Check a finished device. All twelve IDs should answer:

```bash
dexremo-teleop scan --port /dev/ttyACM0
```

## 3. Calibrate

Calibrate the hand and the leader once after assembly, and again after you replace a servo or take a joint apart.

```bash
dexremo-teleop calibrate --port /dev/ttyACM0 --name follower
dexremo-teleop calibrate --port /dev/ttyACM1 --name leader
```

The script turns the torque off and walks you through two steps:

1. Put the device in the [zero pose](../sim/README.md#zero-pose) and press ENTER. The script stores this pose in each servo as its zero offset, so that it reads 2048.
2. Move every joint through its full range of motion and press ENTER. The script records each joint's range; teleoperation never commands the hand outside it.

The result is saved to `~/.dexremo/calibration/<name>.json`. When the program connects, it checks that the offsets stored in the servos match this file, and asks you to calibrate again if they do not.

## 4. Check the joint signs

```bash
dexremo-teleop monitor --port /dev/ttyACM0 --name follower
```

In the zero pose every joint should read about 0°. Move each joint in its +q direction from the [joint table](../sim/README.md#joints). The reading should go up. On a hand built as in the assembly guide, every servo turns the same way as the simulation model, so the default signs (all +1) are already right. With the hand mounted palm down:

- `mcp`, `ip`: lifting the finger towards the palm (up) is positive;
- `cmc1`: seen from the back of the hand (the flange side), counter-clockwise is positive;
- `cmc2`: seen from outside looking towards the palm centre, clockwise is positive.

The [joint convention figure](../sim/docs/joint_convention.png) shows each one.

If a joint goes the wrong way (for example, a servo mounted the other way round), set its `"sign"` to `-1` in the calibration file.

The signs matter for recorded data and for the simulation model. Teleoperation maps the leader's joint angles onto the hand's, so if the leader and the hand use the same signs, the hand follows correctly either way.

## 5. Teleoperate

```bash
dexremo-teleop teleop --leader-port /dev/ttyACM1 --follower-port /dev/ttyACM0
```

- At the start, the hand moves slowly to the leader's pose (`--ramp`, 2 s by default). Then it follows the leader at 30 Hz (`--fps`).
- Commands are clipped to each joint's calibrated range (`--margin` ticks inside it) and to a maximum joint speed (`--max-speed`, rad/s).
- Ctrl+C stops. The hand's torque is turned off; add `--hold` to keep it on.
- `--viewer` opens a 3D window with the hand's live pose and a force arrow at each fingertip (right red, middle green, left blue; 2.5 cm per newton). It runs in its own thread and does not slow down the control loop.
- To watch one device without teleoperation (torque off, move it by hand): `dexremo-teleop view --port /dev/ttyACM1 --name leader`.

## Force sensors

Without force-sensing fingertips, leave `--force` at its default, `none`.

To try the display and the data flow without sensors, `--force mock` makes up fingertip forces:

```bash
dexremo-teleop teleop --leader-port /dev/ttyACM1 --follower-port /dev/ttyACM0 --viewer --force mock
```

The code does not include a driver for any particular transmitter. To use force-sensing fingertips:

1. Copy [`examples/my_transmitter.py`](examples/my_transmitter.py) and fill in `read_channels()` and `zero()` from your transmitter's datasheet. `read_channels()` returns the nine readings in the channel order of the [calibration method](../hardware/force_calibration.md#step-1-label-and-wire-the-load-cells) (1+X, 1+Y, 1−Y, 2+X, …); `zero()` sends the datasheet's zeroing command.
2. Once a day after power-on, zero the transmitter with nothing touching the fingertips, then check the readings:
   ```bash
   dexremo-teleop force-zero --force my_transmitter.py:MyTransmitter
   dexremo-teleop force-check --force my_transmitter.py:MyTransmitter
   ```
   Do not zero more often: each zeroing writes the transmitter's flash memory, which allows only a limited number of writes.
3. Put each fingertip's fit from [step 6](../hardware/force_calibration.md#step-6-fit-the-mapping) in a JSON file:
   ```json
   {"right": {"K": [[...], [...], [...]], "c": [0, 0, 0]}, "mid": {...}, "left": {...}}
   ```
4. Teleoperate with it:
   ```bash
   dexremo-teleop teleop ... --force my_transmitter.py:MyTransmitter --force-calibration my_force_calib.json
   ```

The terminal shows each fingertip's force in its sensor frame and in the wrist frame (F_wrist = R(q) F_sensor, with R from the simulation model's forward kinematics; needs MuJoCo). The sensor is read in its own thread, so a slow transmitter does not slow down teleoperation.

Any class that subclasses `ForceSensor` in [`dexremo_teleop/force.py`](dexremo_teleop/force.py) and returns one force per fingertip also works.

## Use from Python

```python
from dexremo_teleop import Hand, JOINT_NAMES, load_calibration

hand = Hand("/dev/ttyACM0", load_calibration("follower"))
hand.connect()
q = hand.read_q()                 # 12 joint angles, radians, ordered as JOINT_NAMES
hand.configure_follower()
hand.set_torque(True)
hand.write_q(q)                   # clipped to the calibrated range
hand.disconnect()
```

## Not yet included

- recording demonstrations.

## Licence

MIT (see [`LICENSE`](LICENSE)).
