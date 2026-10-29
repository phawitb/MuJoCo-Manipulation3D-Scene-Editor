"""Read completed exports with the official reader and verify synchronization."""

from pathlib import Path
import json
import numpy as np


def verify_dataset(root):
    import av
    import pyarrow.parquet as pq
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from .collection_schema import VIEWS

    root = Path(root)
    collection = json.loads((root / "meta/collection.json").read_text())
    dataset = LeRobotDataset(collection["repo_id"], root=root, video_backend="pyav")
    if len(dataset) == 0:
        raise ValueError("Dataset contains no saved frames")
    rows = []
    for file in sorted((root / "data").rglob("*.parquet")):
        rows.extend(pq.read_table(file).to_pylist())
    rows.sort(key=lambda row: row["index"])
    if len(rows) != len(dataset):
        raise ValueError("LeRobot row count differs from stored frame count")
    for view in VIEWS:
        total = 0
        for video in sorted(
            (root / "videos" / f"observation.images.{view}").rglob("*.mp4")
        ):
            with av.open(str(video)) as container:
                stream = container.streams.video[0]
                total += stream.frames or sum(1 for _ in container.decode(video=0))
        if total != len(dataset):
            raise ValueError(
                f"{view} has {total} video frames for {len(dataset)} observations"
            )
    indices = sorted({row["episode_index"] for row in rows})
    for index in indices:
        episode = [row for row in rows if row["episode_index"] == index]
        trace = np.load(root / f"trajectories/episode_{index:06}.npz")
        steps = trace["sample_steps"]
        np.testing.assert_allclose(
            [r["timestamp"] for r in episode], trace["time"][steps], atol=1e-5
        )
        np.testing.assert_allclose(
            [r["observation.state"] for r in episode], trace["qpos"][steps], atol=1e-6
        )
        np.testing.assert_allclose(
            [r["action"] for r in episode], trace["control"][steps], atol=1e-6
        )
        for row in (episode[0], episode[len(episode) // 2], episode[-1]):
            frame = dataset[row["index"]]
            for view in VIEWS:
                image = frame[f"observation.images.{view}"]
                if tuple(image.shape)[0] != 3 or not bool(image.isfinite().all()):
                    raise ValueError(f"Invalid decoded image for {view}")
    return {
        "format": "LeRobot v3.0",
        "lerobot_version": "0.6.1",
        "frames": len(dataset),
        "episodes": len(indices),
        "cameras": list(VIEWS),
        "verified": True,
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(verify_dataset(sys.argv[1])))
