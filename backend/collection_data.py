"""Time-aligned LeRobot features and a lossless dense controller trace."""

from pathlib import Path
import json
import os
import mujoco
import numpy as np
from .collection_schema import VIEWS

JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
TCP = ["x", "y", "z", "qw", "qx", "qy", "qz"]


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False))
    os.replace(temporary, path)


def features(width, height, joint_names):
    return {
        "observation.state": {"dtype": "float32", "shape": (6,), "names": joint_names},
        "observation.velocity": {
            "dtype": "float32",
            "shape": (6,),
            "names": joint_names,
        },
        "observation.effort": {"dtype": "float32", "shape": (6,), "names": joint_names},
        "observation.tcp": {"dtype": "float32", "shape": (7,), "names": TCP},
        "observation.sim_time": {
            "dtype": "float64",
            "shape": (1,),
            "names": ["seconds"],
        },
        "action": {"dtype": "float32", "shape": (6,), "names": joint_names},
        **{
            f"observation.images.{view}": {
                "dtype": "video",
                "shape": (height, width, 3),
                "names": ["height", "width", "channels"],
            }
            for view in VIEWS
        },
    }


def signals(sim):
    data = sim.data
    site = sim.model.site("gripperframe").id
    quat = np.empty(4)
    mujoco.mju_mat2Quat(quat, data.site_xmat[site])
    return {
        "time": float(data.time),
        "qpos": data.qpos[:6].copy(),
        "qvel": data.qvel[:6].copy(),
        "effort": data.qfrc_actuator[:6].copy(),
        "control": data.ctrl[:6].copy(),
        "tcp": np.r_[data.site_xpos[site], quat],
    }


class EpisodeRecorder:
    def __init__(self, dataset, renderer, config, on_sample=None, cancelled=None):
        self.dataset, self.renderer, self.config = dataset, renderer, config
        self.on_sample, self.cancelled = on_sample, cancelled
        self.trace = {
            key: [] for key in ("time", "qpos", "qvel", "effort", "control", "tcp")
        }
        self.sample_steps = []
        self.frames = 0

    def before_step(self, sim):
        if self.cancelled and self.cancelled():
            raise CollectionCancelled()
        step = len(self.trace["time"])
        values = signals(sim)
        for key, value in values.items():
            self.trace[key].append(value)
        if step % (1000 // self.config.fps):
            return
        frame = {
            "observation.state": values["qpos"].astype(np.float32),
            "observation.velocity": values["qvel"].astype(np.float32),
            "observation.effort": values["effort"].astype(np.float32),
            "observation.tcp": values["tcp"].astype(np.float32),
            "observation.sim_time": np.array([values["time"]], dtype=np.float64),
            "action": values["control"].astype(np.float32),
            "task": self.config.task,
        }
        # No simulation stepping occurs between the five native camera captures.
        for view in VIEWS:
            frame[f"observation.images.{view}"] = self.renderer.capture(view)
        self.dataset.add_frame(frame)
        self.sample_steps.append(step)
        self.frames += 1
        if self.on_sample:
            self.on_sample(
                self.frames, values["time"], frame["observation.images.main"]
            )

    def save_trace(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            **{k: np.asarray(v) for k, v in self.trace.items()},
            sample_steps=np.asarray(self.sample_steps, dtype=np.int64),
        )


class CollectionCancelled(Exception):
    pass
