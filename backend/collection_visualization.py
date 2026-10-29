"""Read-only preview index for collected LeRobot v3 datasets, including offsets."""

from pathlib import Path
import json
import subprocess
import threading

import numpy as np
from .collection_data import atomic_json

INDEX_FILE = "meta/collection-viewer-v1.json"
_index_lock = threading.Lock()


def contained_file(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Dataset file is missing or outside the dataset")
    return path


def build_index(root):
    # Only called inside the isolated collection runtime (PyArrow dependency).
    import pyarrow.parquet as pq

    root = Path(root)
    info = json.loads((root / "meta/info.json").read_text())
    manifest = json.loads((root / "meta/collection.json").read_text())
    cameras = [
        key.removeprefix("observation.images.")
        for key, feature in info["features"].items()
        if key.startswith("observation.images.") and feature["dtype"] == "video"
    ]
    recipes = {
        a["dataset_episode_index"]: a
        for a in manifest["attempts"]
        if a.get("dataset_episode_index") is not None
    }
    episodes = []
    for file in sorted((root / "meta/episodes").rglob("*.parquet")):
        for row in pq.read_table(file).to_pylist():
            index = int(row["episode_index"])
            recipe = recipes[index]
            videos = {}
            for view in cameras:
                key = f"observation.images.{view}"
                prefix = f"videos/{key}"
                path = info["video_path"].format(
                    video_key=key,
                    chunk_index=int(row[prefix + "/chunk_index"]),
                    file_index=int(row[prefix + "/file_index"]),
                )
                contained_file(root, path)
                videos[view] = {
                    "path": path,
                    "start": float(row[prefix + "/from_timestamp"]),
                    "end": float(row[prefix + "/to_timestamp"]),
                }
            episodes.append(
                {
                    "index": index,
                    "frames": int(row["length"]),
                    "seed": recipe["seed"],
                    "outcome": recipe["outcome"],
                    "success": recipe["success"],
                    "videos": videos,
                }
            )
    result = {
        "version": 1,
        "name": manifest["config"]["name"],
        "scene_name": manifest.get("scene_name", "Collected scene"),
        "task": manifest["config"]["task"],
        "fps": info["fps"],
        "cameras": cameras,
        "camera_projection_version": manifest.get("camera_projection_version", 1),
        "joint_names": info["features"]["observation.state"]["names"],
        "episodes": sorted(episodes, key=lambda e: e["index"]),
    }
    if len(episodes) != info["total_episodes"]:
        raise ValueError("Episode metadata count differs from dataset")
    atomic_json(root / INDEX_FILE, result)
    return result


def load_index(root, runtime):
    path = Path(root) / INDEX_FILE
    with _index_lock:
        if not path.exists():
            result = subprocess.run(
                [str(runtime), "-m", "backend.collection_visualization", str(root)],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode:
                raise ValueError(
                    "Cannot prepare dataset preview: " + result.stderr[-1000:]
                )
        return json.loads(contained_file(root, INDEX_FILE).read_text())


def find_episode(index, episode):
    return next(
        (entry for entry in index["episodes"] if entry["index"] == episode), None
    )


def episode_signals(root, entry):
    path = contained_file(root, f"trajectories/episode_{entry['index']:06}.npz")
    with np.load(path, allow_pickle=False) as trace:
        steps = trace["sample_steps"]
        if len(steps) != entry["frames"]:
            raise ValueError("Trace length differs from episode")
        return {
            "episode": entry["index"],
            "time": trace["time"][steps].tolist(),
            **{
                name: trace[key][steps].tolist()
                for name, key in (
                    ("state", "qpos"),
                    ("action", "control"),
                    ("velocity", "qvel"),
                    ("effort", "effort"),
                    ("tcp", "tcp"),
                )
            },
        }


if __name__ == "__main__":
    import sys

    build_index(sys.argv[1])
