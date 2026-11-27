"""Command-line tools: dexremo-teleop <command> --help."""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import threading
import time

import numpy as np

from .force import FINGERTIPS, BackgroundReader, NoForceSensor, load_force_sensor
from .hand import Hand, JointCalibration, calibration_path, load_calibration, save_calibration
from .joints import DEFAULT_SIGNS, FINGER_JOINTS, FINGERS, JOINT_NAMES, SERVO_IDS
from .servo_bus import CENTER, DEFAULT_BAUDRATE, ServoBus, ServoError, decode_offset
from .teleop_loop import TeleopLoop, TeleopProcess

ID_TO_JOINT = {i: n for n, i in SERVO_IDS.items()}
UP = "\033[F"  # move the cursor to the start of the previous line
CLEAR = "\033[K"


class _EnterPressed:
    """Becomes true when the user presses ENTER, without blocking the caller."""

    def __init__(self):
        self._event = threading.Event()
        threading.Thread(target=self._wait, daemon=True).start()

    def _wait(self):
        sys.stdin.readline()
        self._event.set()

    def __bool__(self):
        return self._event.is_set()


def _redraw(lines: list[str], first: bool) -> None:
    # Lines longer than the terminal wrap, and moving the cursor up no longer lands on them.
    width = shutil.get_terminal_size((100, 24)).columns - 1
    if not first:
        sys.stdout.write(UP * len(lines))
    sys.stdout.write("".join(line[:width] + CLEAR + "\n" for line in lines))
    sys.stdout.flush()


def _joint_table(values: np.ndarray, fmt: str) -> list[str]:
    head = "        " + "".join(f"{j:>9}" for j in FINGER_JOINTS)
    rows = [head]
    for f, finger in enumerate(FINGERS):
        cells = "".join(format(v, fmt).rjust(9) for v in values[4 * f : 4 * f + 4])
        rows.append(f"{finger:<8}{cells}")
    return rows


# -- ports, scan, set-id ------------------------------------------------------------


def cmd_ports(args) -> None:
    from serial.tools import list_ports

    ports = sorted(list_ports.comports(), key=lambda p: p.device)
    if not ports:
        print("No serial ports found.")
    for p in ports:
        print(f"{p.device:<16} {p.description}  [{p.hwid}]")
    print("\nUnplug one board and run this again to see which port is which.")


def cmd_scan(args) -> None:
    ids = range(0, 254) if args.all else range(1, 21)
    with ServoBus(args.port, args.baudrate) as bus:
        found = bus.scan(ids)
        if not found:
            print(f"No servo answered on {args.port} at {args.baudrate} baud (IDs {ids.start}-{ids.stop - 1}).")
            return
        multi = []
        print(f"{'ID':>3}  {'joint':<11} {'model':>5} {'position':>8} {'offset':>6} {'voltage':>7} {'temp':>5}")
        for i, model in found.items():
            pos = bus.read(i, "Present_Position")
            if pos >= 4096:
                multi.append(i)
            off = decode_offset(bus.read(i, "Homing_Offset"))
            volt = bus.read(i, "Present_Voltage") / 10
            temp = bus.read(i, "Present_Temperature")
            print(f"{i:>3}  {ID_TO_JOINT.get(i, '-'):<11} {model:>5} {pos:>8} {off:>6} {volt:>6.1f}V {temp:>4}C")
        if multi:
            print(f"IDs {multi} report a position outside one turn (0-4095); the code wraps it to one turn.")
        missing = [i for i in SERVO_IDS.values() if i not in found]
        if missing:
            print(f"Missing hand IDs: {missing}")


def cmd_set_id(args) -> None:
    if not 1 <= args.id <= 252:
        sys.exit("--id must be between 1 and 252.")
    with ServoBus(args.port, args.baudrate) as bus:
        print("Scanning... (connect exactly one servo)")
        found = bus.scan()
        if len(found) != 1:
            sys.exit(f"Found {len(found)} servos ({sorted(found)}). Connect exactly one servo and try again.")
        old = next(iter(found))
        if old == args.id:
            print(f"The servo already has ID {old}.")
            return
        bus.write(old, "Lock", 0)
        bus.write(old, "ID", args.id)
        bus.write(args.id, "Lock", 1)
        if bus.ping(args.id) is None:
            sys.exit(f"The servo does not answer on ID {args.id} after the change.")
        print(f"ID {old} -> {args.id} ({ID_TO_JOINT.get(args.id, 'not a hand joint')}).")


# -- calibration -------------------------------------------------------------------


def cmd_calibrate(args) -> None:
    path = calibration_path(args.name)
    hand = Hand(args.port, baudrate=args.baudrate)
    hand.connect()
    try:
        print(f"Calibrating the device on {args.port}. The result goes to {path}.")
        print("Torque is off: you can move every joint by hand.\n")
        hand.reset_offsets_and_limits()

        input(
            "Step 1/2. Move the device into the ZERO POSE (sim/README.md#zero-pose):\n"
            "  middle finger straight out, side fingers turned outwards, every finger bent into a hook.\n"
            "Hold it there and press ENTER..."
        )
        offsets = hand.set_zero_here()
        ticks = hand.read_ticks()
        off_center = [n for n, t in zip(JOINT_NAMES, ticks) if abs(int(t) - CENTER) > 20]
        if off_center:
            print(f"Warning: {off_center} did not read the zero pose back; did the device move?")

        print(
            "\nStep 2/2. Move EVERY joint slowly through its full range of motion, one by one.\n"
            "Press ENTER when done.\n"
        )
        lo = ticks.copy()
        hi = ticks.copy()
        done = _EnterPressed()
        first = True
        while not done:
            t = hand.read_ticks()
            lo = np.minimum(lo, t)
            hi = np.maximum(hi, t)
            span = np.degrees((hi - lo) / 4096 * 2 * math.pi)
            _redraw(["range of motion seen so far, degrees:", *_joint_table(span, ".0f")], first)
            first = False
            time.sleep(0.02)

        small = [n for n, a, b in zip(JOINT_NAMES, lo, hi) if (b - a) < 200]
        if small:
            print(f"Warning: {small} moved less than 18 degrees. Calibrate again if that is wrong.")

        calib = {
            n: JointCalibration(
                id=SERVO_IDS[n],
                homing_offset=offsets[n],
                range_min=int(lo[k]),
                range_max=int(hi[k]),
                sign=DEFAULT_SIGNS[n],
            )
            for k, n in enumerate(JOINT_NAMES)
        }
        print(f"\nSaved {save_calibration(calib, args.name)}")
        print(f"Next: check the joint signs with `dexremo-teleop monitor --port {args.port} --name {args.name}`.")
    finally:
        hand.disconnect()


def cmd_monitor(args) -> None:
    calib = load_calibration(args.name) if args.name else None
    hand = Hand(args.port, calib, baudrate=args.baudrate)
    hand.connect()
    try:
        hand.bus.set_torque(hand.ids, False)
        print("Torque is off. Move the joints by hand; Ctrl+C to stop.")
        if calib:
            print("Each joint should read about 0 in the zero pose, and go positive in the +q direction")
            print("of sim/README.md#joints. If one goes the wrong way, flip its \"sign\" in")
            print(f"{calibration_path(args.name)}.\n")
        first = True
        while True:
            if calib:
                lines = ["joint angles, degrees:", *_joint_table(np.degrees(hand.read_q()), "+.1f")]
            else:
                lines = ["raw positions, ticks (no calibration given):", *_joint_table(hand.read_ticks(), "d")]
            _redraw(lines, first)
            first = False
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()
    finally:
        hand.disconnect()


# -- teleoperation -------------------------------------------------------------------


def _format_forces(forces, wrist=None) -> list[str]:
    if forces is None:
        return []
    head = "fingertip force, N       sensor frame: Fx      Fy      Fz"
    if wrist is not None:
        head += "    wrist frame: Fx      Fy      Fz"
    rows = [head]
    for f in FINGERTIPS:
        row = f"  {f:<34}" + " ".join(f"{v:+7.2f}" for v in forces[f])
        if wrist is not None:
            row += " " * 17 + " ".join(f"{v:+7.2f}" for v in wrist[f])
        rows.append(row)
    return rows


def _optional_kinematics():
    """Forward kinematics for wrist-frame forces, or None without MuJoCo."""
    try:
        from .kinematics import HandKinematics

        return HandKinematics()
    except ImportError:
        return None


def _connect_pair(args) -> tuple[Hand, Hand]:
    leader = Hand(args.leader_port, load_calibration(args.leader_name), baudrate=args.baudrate)
    follower = Hand(args.follower_port, load_calibration(args.follower_name), baudrate=args.baudrate)
    leader.connect()
    try:
        follower.connect()
    except Exception:
        leader.disconnect()
        raise
    return leader, follower


def _start_loop(leader: Hand, follower: Hand, args, fps: float, read_hand: bool = False) -> TeleopLoop:
    leader.configure_leader()
    follower.configure_follower()
    follower.set_torque(True)
    loop = TeleopLoop(leader, follower, fps, args.max_speed, args.margin, read_hand=read_hand)
    print(f"Moving the hand to the leader's pose over {args.ramp:.1f} s...")
    loop.ramp(args.ramp)
    return loop.start()


def _release_pair(leader: Hand, follower: Hand, hold: bool) -> None:
    follower.disconnect(disable_torque=not hold)
    leader.disconnect()
    if hold:
        print("The hand keeps its torque on (--hold). Power it off or run `monitor` to release it.")


def cmd_teleop(args) -> None:
    sensor = load_force_sensor(args.force, args.force_calibration)
    has_force = not isinstance(sensor, NoForceSensor)
    kin = _optional_kinematics() if has_force else None
    viewer = None
    if args.viewer:
        from .viewer import HandViewer

        viewer = HandViewer()

    cameras, display = _open_cameras(args), None
    leader, follower = _connect_pair(args)
    sensor.connect()
    reader = BackgroundReader(sensor).start() if has_force else None
    loop = None
    try:
        loop = _start_loop(leader, follower, args, args.fps)
        if viewer is not None:
            viewer.start()
        if args.display:
            from .display import RerunDisplay

            display = RerunDisplay(cameras, loop, reader).start()
        print(f"Teleoperating at {args.fps:g} Hz. Ctrl+C to stop.\n")
        first = True
        last_draw = 0.0
        while True:
            if loop.error is not None:
                raise loop.error
            snap = loop.latest()
            forces = None
            if reader is not None:
                forces, age = reader.latest()
                if age > 0.5:
                    forces = None  # stale: the sensor stopped answering
            if viewer is not None and snap is not None:
                viewer.update(snap.q_command, forces)
            now = time.perf_counter()
            if snap is not None and now - last_draw > 0.2:
                status = f"loop {loop.rate:5.1f} Hz, longest cycle {loop.pop_worst_cycle_ms():4.1f} ms"
                if reader is not None:
                    status += f", force sensor {reader.rate:5.1f} Hz" + (" (no data)" if forces is None else "")
                lines = [status, "leader joint angles, degrees:", *_joint_table(np.degrees(snap.q_leader), "+.1f")]
                if forces is not None:
                    wrist = None
                    if kin is not None:
                        kin.update(snap.q_command)
                        wrist = kin.forces_to_wrist(forces)
                    lines += _format_forces(forces, wrist)
                _redraw(lines, first)
                first = False
                last_draw = now
            time.sleep(1 / 60)
    except KeyboardInterrupt:
        print()
    finally:
        if display is not None:
            display.close()
        if loop is not None:
            loop.stop()
        if viewer is not None:
            viewer.close()
        if reader is not None:
            reader.stop()
        sensor.close()
        for cam in cameras.values():
            cam.close()
        _release_pair(leader, follower, args.hold)


def _open_cameras(args) -> dict:
    from .cameras import Camera, parse_camera_spec

    cameras = {}
    try:
        for spec in args.camera:
            name, dev = parse_camera_spec(spec)
            if name in cameras:
                raise ValueError(f"Two cameras are called {name!r}.")
            cameras[name] = Camera(name, dev, getattr(args, "camera_width", 640), getattr(args, "camera_height", 480),
                                   getattr(args, "camera_fps", 30))
        for cam in cameras.values():
            cam.wait_first_frame()
    except Exception:
        for cam in cameras.values():
            cam.close()
        raise
    return cameras


def cmd_record(args) -> None:
    from .kinematics import HandKinematics
    from .record import Commands, Recorder, dataset_features, finish_dataset, open_dataset

    import importlib.util

    if importlib.util.find_spec("lerobot") is None:
        sys.exit("Recording needs LeRobot (0.4 or later): pip install lerobot")
    if args.fps > args.control_fps:
        print(f"Note: recording at {args.fps} Hz, faster than control ({args.control_fps:g} Hz): joint data repeats.")
    if args.camera and args.fps > args.camera_fps:
        print(f"Note: recording at {args.fps} Hz, faster than the cameras ({args.camera_fps} fps): images repeat.")

    sensor = load_force_sensor(args.force, args.force_calibration)
    has_force = not isinstance(sensor, NoForceSensor)
    kin = HandKinematics(args.model)
    if has_force and not kin.has_sensors:
        sys.exit(f"{args.model} has no fingertip force sensors; use sim/mjcf/dexremo_hand.xml.")

    cameras = {}
    loop = reader = viewer = dataset = display = None
    try:
        cameras = _open_cameras(args)
        if not cameras:
            print("Warning: recording without cameras (no --camera given).")

        features = dataset_features(cameras, has_force)
        dataset = open_dataset(args.repo_id, args.root, args.fps, features, args.resume, 4 * len(cameras))
        print(f"Dataset: {dataset.root} ({dataset.num_episodes} episodes so far)")

        sensor.connect()
        reader = BackgroundReader(sensor).start() if has_force else None
        # The control loop runs in its own process, so that video encoding between
        # episodes cannot stall it. It opens the servo ports there.
        print(f"Moving the hand to the leader's pose over {args.ramp:.1f} s...")
        loop = TeleopProcess(
            args.leader_port, load_calibration(args.leader_name), args.follower_port,
            load_calibration(args.follower_name), args.baudrate, args.control_fps, args.max_speed, args.margin,
            args.ramp, read_hand=True, hold=args.hold,
        ).start()
        if args.viewer:
            from .viewer import HandViewer

            viewer = HandViewer()
            viewer.start()

        if args.display:
            from .display import RerunDisplay

            display = RerunDisplay(cameras, loop, reader).start()
        recorder = Recorder(loop, kin, cameras, reader, dataset, args.task, args.fps, viewer)
        recorder.start_camera_clock()
        commands = Commands()
        print(
            f"\nTask: {args.task}\n"
            "Keys (type, then ENTER):  ENTER = start / finish the episode early / end the reset,\n"
            "                          r = discard this episode and record it again,\n"
            "                          q = save the current episode and stop.\n"
        )
        recorded = 0
        result = recorder.run_phase(float("inf"), commands, False, f"Ready: ENTER starts episode {dataset.num_episodes}")
        print()
        while result != "quit" and recorded < args.episodes:
            index = dataset.num_episodes
            result = recorder.run_phase(args.episode_time, commands, True, f"Episode {index}")
            t_end = time.perf_counter()
            print()
            frames = dataset.episode_buffer["size"] if dataset.episode_buffer else 0
            if result == "redo":
                dataset.clear_episode_buffer()
                print(f"Episode {index} discarded; it will be recorded again after the reset.")
            elif frames:
                print(f"Saving episode {index} ({frames} frames, encoding video). Teleoperation keeps running: "
                      "reset the scene meanwhile.")
                t_save = time.perf_counter()
                dataset.save_episode()
                recorded += 1
                print(f"Saved episode {index} in {time.perf_counter() - t_save:.0f} s. "
                      f"{recorded}/{args.episodes} this session.")
            if recorder.stale_force_frames:
                print(f"Warning: {recorder.stale_force_frames} frames had no fresh force reading (stored as NaN).")
                recorder.stale_force_frames = 0
            if result == "quit" or recorded >= args.episodes:
                break
            # The reset time counts from the end of the episode: saving and resetting overlap.
            elapsed = time.perf_counter() - t_end
            result = recorder.run_phase(max(0.0, args.reset_time - elapsed), commands, False,
                                        "Reset the scene (ENTER when ready)")
            print()
        print(f"Done: {dataset.num_episodes} episodes in {dataset.root}")
    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C). The episode in progress was not saved.")
        if dataset is not None and dataset.episode_buffer:
            dataset.clear_episode_buffer()
    finally:
        if display is not None:
            display.close()
        if loop is not None:
            loop.stop()
        if dataset is not None:
            finish_dataset(dataset)
            if not args.resume and dataset.num_episodes == 0:
                # Nothing was saved: remove the empty dataset this run created, so the
                # next run can use the same --repo-id/--root without --resume.
                import shutil

                shutil.rmtree(dataset.root, ignore_errors=True)
        if viewer is not None:
            viewer.close()
        if reader is not None:
            reader.stop()
        sensor.close()
        for cam in cameras.values():
            cam.close()
        if args.hold and loop is not None:
            print("The hand keeps its torque on (--hold). Power it off or run `monitor` to release it.")


def cmd_view(args) -> None:
    from .viewer import HandViewer

    hand = Hand(args.port, load_calibration(args.name), baudrate=args.baudrate)
    sensor = load_force_sensor(args.force, args.force_calibration)
    hand.connect()
    sensor.connect()
    reader = None if isinstance(sensor, NoForceSensor) else BackgroundReader(sensor).start()
    viewer = HandViewer()
    try:
        hand.bus.set_torque(hand.ids, False)
        viewer.start()
        print("Torque is off; move the device by hand. Close the window or press Ctrl+C to stop.")
        while viewer.is_running:
            viewer.update(hand.read_q(), reader.latest()[0] if reader else None)
            time.sleep(1 / 60)
    except KeyboardInterrupt:
        print()
    finally:
        viewer.close()
        if reader is not None:
            reader.stop()
        sensor.close()
        hand.disconnect()


def cmd_force_zero(args) -> None:
    sensor = load_force_sensor(args.force, args.force_calibration)
    if isinstance(sensor, NoForceSensor):
        sys.exit("No force sensor given (--force).")
    input("Make sure nothing touches the fingertips, then press ENTER to zero the transmitter...")
    sensor.connect()
    try:
        sensor.zero()
        print("Zeroed. Do this once a day after power-on, not more: each zeroing writes the transmitter's flash.")
    except NotImplementedError as e:
        sys.exit(f"Error: {e} Implement zero() in your ForceSensor class (see examples/my_transmitter.py).")
    finally:
        sensor.close()


def cmd_force_check(args) -> None:
    sensor = load_force_sensor(args.force, args.force_calibration)
    sensor.connect()
    try:
        forces = sensor.read()
        if forces is None:
            print("No force sensor (--force none).")
            return
        first = True
        while True:
            _redraw(_format_forces(sensor.read()), first)
            first = False
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()
    finally:
        sensor.close()


def _default_model():
    from pathlib import Path

    return Path(__file__).resolve().parents[2] / "sim" / "mjcf" / "dexremo_hand.xml"


# -- entry point -------------------------------------------------------------------


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="dexremo-teleop", description="DexRemo hand: servo tools and teleoperation.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_text):
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.set_defaults(func=func)
        return p

    def bus_args(p):
        p.add_argument("--port", required=True, help="serial port of the servo driver board, e.g. /dev/ttyACM0")
        p.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)

    add("ports", cmd_ports, "List serial ports.")

    p = add("scan", cmd_scan, "List the servos on a port with their position, voltage and temperature.")
    bus_args(p)
    p.add_argument("--all", action="store_true", help="scan IDs 0-253 instead of 1-20")

    p = add("set-id", cmd_set_id, "Give a single connected servo a new ID.")
    bus_args(p)
    p.add_argument("--id", type=int, required=True, help="new ID (see the servo ID map)")

    p = add("calibrate", cmd_calibrate, "Zero-pose and range calibration of the hand or the leader.")
    bus_args(p)
    p.add_argument("--name", required=True, help="calibration name, e.g. follower or leader, or a .json path")

    p = add("monitor", cmd_monitor, "Show live joint angles with torque off (for checking signs).")
    bus_args(p)
    p.add_argument("--name", help="calibration name; without it, raw ticks are shown")

    p = add("teleop", cmd_teleop, "Leader-follower teleoperation.")
    p.add_argument("--leader-port", required=True)
    p.add_argument("--follower-port", required=True)
    p.add_argument("--leader-name", default="leader", help="leader calibration name (default: leader)")
    p.add_argument("--follower-name", default="follower", help="hand calibration name (default: follower)")
    p.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    p.add_argument("--fps", type=float, default=30.0, help="control rate in Hz (default: 30)")
    p.add_argument("--max-speed", type=float, default=8.0, help="max joint speed sent to the hand, rad/s")
    p.add_argument("--margin", type=int, default=10, help="keep this many ticks inside the calibrated range")
    p.add_argument("--ramp", type=float, default=2.0, help="seconds to move to the leader's pose at start")
    p.add_argument("--hold", action="store_true", help="keep the hand's torque on after stopping")
    p.add_argument("--force", default="none", help="'none' (default), 'mock', or file.py:ClassName of a ForceSensor")
    p.add_argument("--force-calibration", help="JSON file with K and c per fingertip")

    p.add_argument("--viewer", action="store_true", help="show the hand and fingertip forces in a 3D window (needs mujoco)")
    p.add_argument("--camera", action="append", default=[], metavar="NAME=DEVICE",
                   help="a camera to show with --display, e.g. --camera wrist=/dev/video4")
    p.add_argument("--display", action="store_true", help="show the cameras, joint angles and forces live in Rerun")

    p = add("record", cmd_record, "Record teleoperated demonstrations as a LeRobot dataset.")
    p.add_argument("--leader-port", required=True)
    p.add_argument("--follower-port", required=True)
    p.add_argument("--leader-name", default="leader", help="leader calibration name (default: leader)")
    p.add_argument("--follower-name", default="follower", help="hand calibration name (default: follower)")
    p.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    p.add_argument("--repo-id", required=True, help="dataset name, e.g. yourname/dexremo_a1")
    p.add_argument("--root", help="dataset folder (default: LeRobot's cache, ~/.cache/huggingface/lerobot/<repo-id>)")
    p.add_argument("--task", required=True, help='task description stored with every frame, e.g. "Remove the barnacle"')
    p.add_argument("--episodes", type=int, default=20, help="episodes to record in this session (default: 20)")
    p.add_argument("--episode-time", type=float, default=120.0, help="seconds per episode (default: 120)")
    p.add_argument("--reset-time", type=float, default=30.0, help="seconds to reset between episodes (default: 30)")
    p.add_argument("--resume", action="store_true", help="add episodes to an existing dataset")
    p.add_argument("--fps", type=int, default=15,
                   help="recording rate in Hz (default: 15, as in the paper; about 10 up to the camera rate works)")
    p.add_argument("--control-fps", type=float, default=30.0, help="teleoperation rate in Hz (default: 30)")
    p.add_argument("--camera", action="append", default=[], metavar="NAME=DEVICE",
                   help="a camera, e.g. --camera left=/dev/video0 --camera right=/dev/video2 --camera wrist=/dev/video4")
    p.add_argument("--camera-width", type=int, default=640)
    p.add_argument("--camera-height", type=int, default=480)
    p.add_argument("--camera-fps", type=int, default=30)
    p.add_argument("--force", default="none", help="'none' (default), 'mock', or file.py:ClassName of a ForceSensor")
    p.add_argument("--force-calibration", help="JSON file with K and c per fingertip")
    p.add_argument("--model", default=str(_default_model()), help="MJCF model for the fingertip poses")
    p.add_argument("--max-speed", type=float, default=8.0, help="max joint speed sent to the hand, rad/s")
    p.add_argument("--margin", type=int, default=10, help="keep this many ticks inside the calibrated range")
    p.add_argument("--ramp", type=float, default=2.0, help="seconds to move to the leader's pose at start")
    p.add_argument("--hold", action="store_true", help="keep the hand's torque on after stopping")
    p.add_argument("--viewer", action="store_true", help="also show the 3D view")
    p.add_argument("--display", action="store_true", help="show the cameras, joint angles and forces live in Rerun")

    p = add("view", cmd_view, "Show a device's live pose (and fingertip forces) in a 3D window, torque off.")
    bus_args(p)
    p.add_argument("--name", required=True, help="calibration name, e.g. follower or leader")
    p.add_argument("--force", default="none", help="'none' (default), 'mock' or file.py:ClassName")
    p.add_argument("--force-calibration", help="JSON file with K and c per fingertip")

    p = add("force-check", cmd_force_check, "Print live fingertip forces from a ForceSensor.")
    p.add_argument("--force", required=True, help="'mock' or file.py:ClassName of a ForceSensor")
    p.add_argument("--force-calibration", help="JSON file with K and c per fingertip")

    p = add("force-zero", cmd_force_zero, "Send the transmitter's zeroing command (once a day, after power-on).")
    p.add_argument("--force", required=True, help="file.py:ClassName of a ForceSensor")
    p.add_argument("--force-calibration", help="JSON file with K and c per fingertip")

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ServoError, FileNotFoundError, FileExistsError, ValueError, RuntimeError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
