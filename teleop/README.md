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

## 6. Record demonstrations

Recording writes a [LeRobot](https://github.com/huggingface/lerobot) dataset (format v3.0), ready for LeRobot's training scripts. It needs LeRobot 0.4 or later, MuJoCo and OpenCV:

```bash
pip install lerobot
pip install -e ".[record]"
```

Find your cameras with `v4l2-ctl --list-devices` (each camera usually shows up as two `/dev/video*` nodes; use the first). Then:

```bash
dexremo-teleop record --leader-port /dev/ttyACM1 --follower-port /dev/ttyACM0 \
    --repo-id yourname/dexremo_a1 --task "Remove the barnacle from the shell" \
    --camera left=/dev/video0 --camera right=/dev/video2 --camera wrist=/dev/video4
```

- Press ENTER to start the first episode. Each episode lasts `--episode-time` seconds (120 by default); ENTER ends it early. Type `r` and ENTER to discard it and record it again, `q` and ENTER to save it and stop.
- After each episode, the videos are encoded while you reset the scene; teleoperation keeps running. The reset lasts `--reset-time` seconds (30 by default; ENTER to go on), counted from the end of the episode, or until encoding is done if that takes longer. Encoding runs at about 80 frames per second per camera: a 60 s episode at 15 Hz with three cameras takes about 35 s.
- `--episodes` is the number to record in this session (20 by default). Add `--resume` to add episodes to an existing dataset in a later session.
- The dataset goes to `~/.cache/huggingface/lerobot/<repo-id>` unless you give `--root`. Nothing is uploaded.
- The recording rate is `--fps` (15 Hz by default, as in the paper; anything from about 10 Hz up to the camera rate works, but encoding time and disk use grow with it). Teleoperation runs at `--control-fps` (30 Hz) in its own process, so recording and video encoding never slow it down.
- With `--force`, the fingertip forces are recorded too. `--display` shows the cameras, joint angles and forces live in [Rerun](https://rerun.io) (installed with LeRobot); `--viewer` shows the 3D view. `teleop` takes `--camera` and `--display` too, to check the cameras without recording.
- **Cameras and USB.** Use MJPG (the default). Webcams reserve USB bandwidth up front, so two webcams behind the same USB 2.0 hub can starve each other (one drops to a few frames per second). Plug each camera into a port on a different USB controller; `lsusb -t` shows which ports share one. In dim light, many webcams lengthen the exposure and deliver fewer frames than their rated 30 fps; the status line shows each camera's real rate.

Each frame holds:

| Key | Size | Content |
|---|---|---|
| `observation.state` | 54 (45 without force) | joint angles (12, rad), joint velocities (12, rad/s), fingertip poses in the wrist frame (3 × x, y, z in m, qx, qy, qz, qw), fingertip forces in the wrist frame (3 × 3, N; with a force sensor) |
| `observation.force_sensor` | 9 | fingertip forces in each sensor frame (with a force sensor) |
| `observation.images.<name>` | 480 × 640 × 3 | one video per camera |
| `action` | 12 | joint angles sent to the hand, rad |

Every value has a name in the dataset's `meta/info.json`. The joint displacement used as the action in the paper is `action` minus the first 12 values of `observation.state`.

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

## Licence

MIT (see [`LICENSE`](LICENSE)).
