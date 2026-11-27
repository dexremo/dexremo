"""Record teleoperated demonstrations as a LeRobot dataset (format v3.0).

Needs LeRobot 0.4 or later (`pip install lerobot`) and `pip install -e ".[record]"` (MuJoCo, OpenCV).

The control loop runs in its own process at --control-fps and never pauses. The
recorder samples it at --fps (15 Hz in the paper) together with the cameras and
the force sensor. Videos are encoded after each episode while the operator resets
the scene; teleoperation keeps running meanwhile.

Each frame holds:

    observation.state    joint angles (12, rad), joint velocities (12, rad/s),
                         fingertip poses in the wrist frame (3 x 7: x, y, z in m, qx, qy, qz, qw),
                         and, with a force sensor, fingertip forces in the wrist frame (3 x 3, N)
    observation.force_sensor   (with a force sensor) the same forces in each sensor frame
    observation.images.<camera>   one video per camera
    action               joint angles sent to the hand (12, rad)

The paper's action, the joint displacement, is action minus the first 12 values
of observation.state.
"""

from __future__ import annotations

import queue
import shutil
import sys
import threading
import time
from pathlib import Path

import numpy as np

from .force import FINGERTIPS, BackgroundReader
from .joints import JOINT_NAMES

AXES = ("x", "y", "z")
POSE = ("x", "y", "z", "qx", "qy", "qz", "qw")


def state_names(with_force: bool) -> list[str]:
    names = [f"{j}.pos" for j in JOINT_NAMES] + [f"{j}.vel" for j in JOINT_NAMES]
    names += [f"{f}_tip.{a}" for f in FINGERTIPS for a in POSE]
    if with_force:
        names += [f"{f}_force_wrist.{a}" for f in FINGERTIPS for a in AXES]
    return names


def dataset_features(cameras: dict, with_force: bool) -> dict:
    names = state_names(with_force)
    features = {
        "observation.state": {"dtype": "float32", "shape": (len(names),), "names": names},
        "action": {"dtype": "float32", "shape": (len(JOINT_NAMES),), "names": [f"{j}.pos" for j in JOINT_NAMES]},
    }
    if with_force:
        features["observation.force_sensor"] = {
            "dtype": "float32",
            "shape": (9,),
            "names": [f"{f}_force_sensor.{a}" for f in FINGERTIPS for a in AXES],
        }
    for name, cam in cameras.items():
        features[f"observation.images.{name}"] = {
            "dtype": "video",
            "shape": (cam.height, cam.width, 3),
            "names": ["height", "width", "channels"],
        }
    return features


class Commands:
    """Reads the operator's keys from the terminal: ENTER, r + ENTER, q + ENTER."""

    def __init__(self):
        self._q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        for line in sys.stdin:
            key = line.strip().lower()
            self._q.put({"": "next", "r": "redo", "q": "quit"}.get(key, "next"))

    def poll(self) -> str | None:
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def clear(self) -> None:
        while self.poll() is not None:
            pass


class Recorder:
    def __init__(self, loop, kinematics, cameras: dict, reader: BackgroundReader | None, dataset, task: str,
                 fps: float, viewer=None):
        self.loop, self.kin, self.cameras, self.reader = loop, kinematics, cameras, reader
        self.dataset, self.task, self.fps, self.viewer = dataset, task, fps, viewer
        self._prev: tuple[float, np.ndarray] | None = None
        self.stale_force_frames = 0

    def _frame(self) -> dict | None:
        snap = self.loop.latest()
        if snap is None or snap.q_hand is None:
            return None
        q = snap.q_hand
        if self._prev is None:
            qd = np.zeros_like(q)
        else:
            t_prev, q_prev = self._prev
            qd = (q - q_prev) / max(snap.t - t_prev, 1e-3)
        self._prev = (snap.t, q)

        self.kin.update(q)
        parts = [q, qd] + [self.kin.tip_pose(f) for f in FINGERTIPS]
        frame = {}
        forces = None
        if self.reader is not None:
            forces, age = self.reader.latest()
            if forces is None or age > 0.5:
                self.stale_force_frames += 1
                forces = {f: np.full(3, np.nan) for f in FINGERTIPS}
            wrist = self.kin.forces_to_wrist(forces)
            parts += [wrist[f] for f in FINGERTIPS]
            frame["observation.force_sensor"] = np.concatenate([forces[f] for f in FINGERTIPS]).astype(np.float32)
        frame["observation.state"] = np.concatenate(parts).astype(np.float32)
        frame["action"] = np.asarray(snap.q_command, dtype=np.float32)
        for name, cam in self.cameras.items():
            image, _ = cam.latest()
            frame[f"observation.images.{name}"] = image
        frame["task"] = self.task
        if self.viewer is not None:
            self.viewer.update(snap.q_command, None if self.reader is None else forces)
        return frame

    def run_phase(self, seconds: float, commands: Commands, record: bool, label: str) -> str:
        """Teleoperate for `seconds`, recording if asked. Returns 'done', 'next', 'redo' or 'quit'."""
        self._prev = None
        period = 1.0 / self.fps
        t0 = time.perf_counter()
        next_tick = t0
        frames = 0
        last_print = 0.0
        while True:
            if self.loop.error is not None:
                raise self.loop.error
            now = time.perf_counter()
            if now - t0 >= seconds:
                return "done"
            cmd = commands.poll()
            if cmd is not None:
                return cmd
            if now >= next_tick:
                next_tick += period
                if next_tick < now:  # fell behind (e.g. a slow disk): do not try to catch up
                    next_tick = now + period
                frame = self._frame()
                if record and frame is not None:
                    self.dataset.add_frame(frame)
                    frames += 1
                elif not record and self.viewer is not None:
                    snap = self.loop.latest()
                    if snap is not None:
                        self.viewer.update(snap.q_command, self.reader.latest()[0] if self.reader else None)
            if now - last_print > 0.5:
                cams = " ".join(f"{n} {c.count / max(now - self._cam_t0, 1e-3):4.1f}fps" for n, c in self.cameras.items())
                status = f"\r{label}: {seconds - (now - t0):5.1f} s left"
                if record:
                    status += f", {frames} frames"
                status += f" | control {self.loop.rate:4.1f} Hz (longest cycle {self.loop.pop_worst_cycle_ms():4.1f} ms) | {cams}"
                if self.reader is not None:
                    status += f" | force {self.reader.rate:4.0f} Hz"
                # Keep the line shorter than the terminal, or \r cannot rewrite it in place.
                width = shutil.get_terminal_size((100, 24)).columns - 1
                sys.stdout.write(status[: width + 1].ljust(width + 1))
                sys.stdout.flush()
                last_print = now
            time.sleep(0.002)

    def start_camera_clock(self) -> None:
        self._cam_t0 = time.perf_counter()
        for cam in self.cameras.values():
            cam.count = 0


def open_dataset(repo_id: str, root: str | None, fps: int, features: dict, resume: bool, image_threads: int):
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    if resume:
        dataset = LeRobotDataset(repo_id, root=root)
        if dataset.fps != fps:
            raise ValueError(f"The dataset was recorded at {dataset.fps} Hz, not {fps} Hz.")
        bookkeeping = {"timestamp", "frame_index", "episode_index", "index", "task_index"}
        existing = {k: tuple(v["shape"]) for k, v in dataset.features.items() if k not in bookkeeping}
        wanted = {k: tuple(v["shape"]) for k, v in features.items()}
        if existing != wanted:
            raise ValueError(
                f"The dataset's features do not match this setup (cameras, force sensor).\n"
                f"  dataset: {existing}\n  now:     {wanted}"
            )
        if image_threads:
            dataset.start_image_writer(num_processes=0, num_threads=image_threads)
        return dataset
    if root is not None and Path(root).exists():
        raise FileExistsError(f"{root} already exists. Use --resume to add episodes, or choose another --root.")
    return LeRobotDataset.create(
        repo_id,
        fps,
        features=features,
        root=root,
        robot_type="dexremo_hand",
        use_videos=True,
        image_writer_threads=image_threads,
    )


def finish_dataset(dataset) -> None:
    if hasattr(dataset, "finalize"):  # LeRobot >= 0.4 needs this to close the data files
        dataset.finalize()
    if getattr(dataset, "image_writer", None) is not None:
        dataset.stop_image_writer()


__all__ = ["Commands", "Recorder", "dataset_features", "finish_dataset", "open_dataset", "state_names"]
