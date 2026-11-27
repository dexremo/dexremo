"""Leader-follower control loop, run in its own thread.

Teleoperation and recording both use it: the loop keeps the hand following the
leader at a steady rate, while the caller samples the latest state whenever it
needs to (display, recording) without slowing the loop down.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np

from .hand import Hand
from .servo_bus import ServoError


@dataclass
class Snapshot:
    t: float  # time.perf_counter() at the end of the cycle
    q_leader: np.ndarray  # leader joint angles, rad
    q_command: np.ndarray  # joint angles sent to the hand, rad (after clipping and speed limit)
    q_hand: np.ndarray | None  # measured hand joint angles, rad (only with read_hand=True)


class TeleopLoop:
    def __init__(
        self,
        leader: Hand,
        hand: Hand,
        fps: float = 30.0,
        max_speed: float = 8.0,
        margin: int = 10,
        read_hand: bool = False,
    ):
        self.leader, self.hand = leader, hand
        self.dt = 1.0 / fps
        self.max_step = max_speed * self.dt
        self.margin = margin
        self.read_hand = read_hand
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.error: Exception | None = None  # set if the loop stopped on an error
        self.rate = fps  # cycles per second, smoothed
        self._worst_ms = 0.0

    def ramp(self, seconds: float) -> None:
        """Move the hand slowly to the leader's pose. Call before start()."""
        start = self.hand.read_q()
        t0 = time.perf_counter()
        while (a := (time.perf_counter() - t0) / seconds) < 1.0:
            self.hand.write_q(start + a * (self.leader.read_q() - start), margin=self.margin)
            time.sleep(self.dt)

    def start(self) -> TeleopLoop:
        self._q_sent = self.hand.write_q(self.leader.read_q(), margin=self.margin)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def latest(self) -> Snapshot | None:
        with self._lock:
            return self._snapshot

    def pop_worst_cycle_ms(self) -> float:
        """Longest cycle (without the sleep) since the last call."""
        worst, self._worst_ms = self._worst_ms, 0.0
        return worst

    def _run(self) -> None:
        errors = 0
        while not self._stop.is_set():
            tick = time.perf_counter()
            try:
                q_leader = self.leader.read_q()
                goal = self._q_sent + np.clip(q_leader - self._q_sent, -self.max_step, self.max_step)
                self._q_sent = self.hand.write_q(goal, margin=self.margin)
                q_hand = self.hand.read_q() if self.read_hand else None
                errors = 0
            except ServoError as e:
                errors += 1
                if errors >= 10:
                    self.error = e
                    return
                continue
            now = time.perf_counter()
            with self._lock:
                self._snapshot = Snapshot(now, q_leader, self._q_sent, q_hand)
            self._worst_ms = max(self._worst_ms, (now - tick) * 1e3)
            elapsed = time.perf_counter() - tick
            if elapsed < self.dt:
                time.sleep(self.dt - elapsed)
            self.rate = 0.9 * self.rate + 0.1 / (time.perf_counter() - tick)


# -- the same loop in its own process ------------------------------------------------
#
# Recording encodes video between episodes, and the video encoder holds Python's
# GIL for up to ~150 ms at a time, which would stall a control thread. In its own
# process the control loop is not affected. The ports are opened in that process;
# the parent only reads the latest snapshot from shared memory.

_N = 12


def _process_main(leader_args, hand_args, loop_kwargs, ramp_s, hold, shared, state, ready, stop, error_q):
    import signal

    from .hand import Hand

    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl+C goes to the parent, which stops us in order
    leader = hand = None
    try:
        leader = Hand(*leader_args[:2], baudrate=leader_args[2])
        hand = Hand(*hand_args[:2], baudrate=hand_args[2])
        leader.connect()
        hand.connect()
        leader.configure_leader()
        hand.configure_follower()
        hand.set_torque(True)
        loop = TeleopLoop(leader, hand, **loop_kwargs)
        loop.ramp(ramp_s)
        loop.start()
        ready.set()
        while not stop.is_set() and loop.running:
            snap = loop.latest()
            if snap is not None:
                with shared.get_lock():
                    shared[0] = snap.t
                    shared[1 : 1 + _N] = snap.q_leader
                    shared[1 + _N : 1 + 2 * _N] = snap.q_command
                    if snap.q_hand is not None:
                        shared[1 + 2 * _N : 1 + 3 * _N] = snap.q_hand
                    state[0] = loop.rate
                    state[1] = max(state[1], loop.pop_worst_cycle_ms())
            time.sleep(0.002)
        loop.stop()
        if loop.error is not None:
            raise loop.error
    except BaseException as e:  # report to the parent, which re-raises it
        error_q.put(f"{type(e).__name__}: {e}")
        ready.set()
    finally:
        if hand is not None:
            hand.disconnect(disable_torque=not hold)
        if leader is not None:
            leader.disconnect()


class TeleopProcess:
    """TeleopLoop in a child process, with the same read-only interface."""

    START_METHOD = "spawn"  # a clean process: no inherited threads or open ports

    def __init__(self, leader_port, leader_calibration, hand_port, hand_calibration, baudrate, fps, max_speed,
                 margin, ramp_s, read_hand=True, hold=False):
        import multiprocessing as mp

        ctx = mp.get_context(self.START_METHOD)
        self._shared = ctx.Array("d", 1 + 3 * _N)
        self._state = ctx.Array("d", 2)  # rate, worst cycle ms
        self._ready, self._stop = ctx.Event(), ctx.Event()
        self._errors = ctx.Queue()
        kwargs = dict(fps=fps, max_speed=max_speed, margin=margin, read_hand=read_hand)
        self._proc = ctx.Process(
            target=_process_main,
            args=((leader_port, leader_calibration, baudrate), (hand_port, hand_calibration, baudrate),
                  kwargs, ramp_s, hold, self._shared, self._state, self._ready, self._stop, self._errors),
            daemon=True,
        )
        self._error: Exception | None = None

    def start(self, timeout: float = 30.0) -> TeleopProcess:
        self._proc.start()
        if not self._ready.wait(timeout):
            raise ServoError("The teleoperation process did not start.")
        self._check()
        if self._error is not None:
            raise self._error
        return self

    def _check(self) -> None:
        if self._error is None and not self._errors.empty():
            self._error = ServoError(self._errors.get())
        if self._error is None and self._ready.is_set() and not self._proc.is_alive():
            self._error = ServoError("The teleoperation process stopped.")

    @property
    def error(self) -> Exception | None:
        self._check()
        return self._error

    @property
    def rate(self) -> float:
        return self._state[0]

    def pop_worst_cycle_ms(self) -> float:
        with self._state.get_lock():
            worst, self._state[1] = self._state[1], 0.0
        return worst

    def latest(self) -> Snapshot | None:
        with self._shared.get_lock():
            v = np.array(self._shared[:])
        if v[0] == 0.0:
            return None
        return Snapshot(v[0], v[1 : 1 + _N], v[1 + _N : 1 + 2 * _N], v[1 + 2 * _N :])

    def stop(self) -> None:
        self._stop.set()
        self._proc.join(timeout=5.0)
        if self._proc.is_alive():
            self._proc.terminate()
