"""Command-line tools: dexremo-teleop <command> --help."""

from __future__ import annotations

import argparse
import math
import sys
import threading
import time

import numpy as np

from .force import FINGERTIPS, load_force_sensor
from .hand import Hand, JointCalibration, calibration_path, load_calibration, save_calibration
from .joints import DEFAULT_SIGNS, FINGER_JOINTS, FINGERS, JOINT_NAMES, SERVO_IDS
from .servo_bus import CENTER, DEFAULT_BAUDRATE, ServoBus, ServoError, decode_offset

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
    if not first:
        sys.stdout.write(UP * len(lines))
    sys.stdout.write("".join(line + CLEAR + "\n" for line in lines))
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


def _format_forces(forces) -> list[str]:
    if forces is None:
        return []
    rows = ["fingertip force, N (sensor frame):     Fx      Fy      Fz"]
    for f in FINGERTIPS:
        fx, fy, fz = forces[f]
        rows.append(f"  {f:<34}{fx:+7.2f} {fy:+7.2f} {fz:+7.2f}")
    return rows


def cmd_teleop(args) -> None:
    leader = Hand(args.leader_port, load_calibration(args.leader_name), baudrate=args.baudrate)
    follower = Hand(args.follower_port, load_calibration(args.follower_name), baudrate=args.baudrate)
    sensor = load_force_sensor(args.force, args.force_calibration)

    leader.connect()
    try:
        follower.connect()
    except Exception:
        leader.disconnect()
        raise
    sensor.connect()

    dt = 1.0 / args.fps
    max_step = args.max_speed * dt
    errors = 0
    try:
        leader.configure_leader()
        follower.configure_follower()
        follower.set_torque(True)

        # Move the follower to the leader's pose slowly before tracking it.
        print(f"Moving the hand to the leader's pose over {args.ramp:.1f} s...")
        start = follower.read_q()
        t0 = time.perf_counter()
        while (a := (time.perf_counter() - t0) / args.ramp) < 1.0:
            goal = start + a * (leader.read_q() - start)
            follower.write_q(goal, margin=args.margin)
            time.sleep(dt)
        sent = follower.write_q(leader.read_q(), margin=args.margin)

        print(f"Teleoperating at {args.fps} Hz. Ctrl+C to stop.\n")
        first = True
        last_draw = 0.0
        loop_hz = float(args.fps)
        while True:
            tick = time.perf_counter()
            try:
                q_leader = leader.read_q()
                goal = sent + np.clip(q_leader - sent, -max_step, max_step)
                sent = follower.write_q(goal, margin=args.margin)
                forces = sensor.read()
                errors = 0
            except ServoError as e:
                errors += 1
                if errors >= 10:
                    raise
                print(f"{e} (retrying)")
                first = True
                continue

            if tick - last_draw > 0.2:
                lines = [f"loop {loop_hz:5.1f} Hz   leader joint angles, degrees:"]
                lines += _joint_table(np.degrees(q_leader), "+.1f")
                lines += _format_forces(forces)
                _redraw(lines, first)
                first = False
                last_draw = tick

            elapsed = time.perf_counter() - tick
            if elapsed < dt:
                time.sleep(dt - elapsed)
            loop_hz = 0.9 * loop_hz + 0.1 / (time.perf_counter() - tick)
    except KeyboardInterrupt:
        print()
    finally:
        sensor.close()
        follower.disconnect(disable_torque=not args.hold)
        leader.disconnect()
        if args.hold:
            print("The hand keeps its torque on (--hold). Power it off or run `monitor` to release it.")


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
    p.add_argument("--force", default="none", help="'none' (default) or file.py:ClassName of a ForceSensor")
    p.add_argument("--force-calibration", help="JSON file with K and c per fingertip")

    p = add("force-check", cmd_force_check, "Print live fingertip forces from a ForceSensor.")
    p.add_argument("--force", required=True, help="file.py:ClassName of a ForceSensor")
    p.add_argument("--force-calibration", help="JSON file with K and c per fingertip")

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ServoError, FileNotFoundError, ValueError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
