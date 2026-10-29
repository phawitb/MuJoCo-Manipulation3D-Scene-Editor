import json
from pathlib import Path
import subprocess

import numpy as np
import pytest
from backend.collection_schema import CollectionConfig
from backend.collection_data import features, EpisodeRecorder
from backend.simulation import Simulation


def test_camera_selection_rejects_empty_unknown_and_duplicates():
    for cameras in ([], ["bad"], ["front", "front"]):
        with pytest.raises(ValueError):
            CollectionConfig(cameras=cameras)
    config = CollectionConfig(cameras=["front", "wrist"])
    schema = features(320, 240, [f"j{i}" for i in range(6)], config.cameras)
    assert {k for k in schema if k.startswith("observation.images.")} == {
        "observation.images.front",
        "observation.images.wrist",
    }


def test_recorder_only_renders_selected_cameras_and_uses_first_for_preview():
    config = CollectionConfig(cameras=["wrist"], fps=10)
    captured, frames, previews = [], [], []

    class Renderer:
        def capture(self, view):
            captured.append(view)
            return np.full((2, 2, 3), 17, dtype=np.uint8)

    class Dataset:
        def add_frame(self, frame):
            frames.append(frame)

    recorder = EpisodeRecorder(
        Dataset(), Renderer(), config, lambda *args: previews.append(args)
    )
    Simulation().step(1, before_step=recorder.before_step)
    assert captured == ["wrist"]
    assert "observation.images.main" not in frames[0]
    assert previews[0][2][0, 0, 0] == 17


def test_real_subset_export_and_viewer_api(tmp_path, monkeypatch):
    from backend.examples import example_scene
    from backend.collection_jobs import RUNTIME
    from fastapi.testclient import TestClient
    from backend.main import app

    if not RUNTIME.exists():
        pytest.skip("Collection runtime not installed")
    job_id = "a" * 32
    directory = tmp_path / job_id
    directory.mkdir()
    (directory / "config.json").write_text(
        json.dumps(
            {
                "id": job_id,
                "scene": example_scene("kalas-cup-front").model_dump(),
                "config": {
                    "name": "viewer-subset",
                    "episodes": 2,
                    "fps": 10,
                    "resolution": "320x240",
                    "max_seconds": 1,
                    "include_failed": True,
                    "cameras": ["front", "wrist"],
                    "variation": {"positions": False},
                },
            }
        )
    )
    result = subprocess.run(
        [str(RUNTIME), "-m", "backend.collection_worker", str(directory)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    root = directory / "dataset"
    verified = json.loads((root / "meta/collection-verification.json").read_text())
    assert verified["cameras"] == ["front", "wrist"]
    assert not (root / "videos/observation.images.main").exists()
    monkeypatch.setenv("SO101_RECORDINGS_DIR", str(tmp_path))
    with TestClient(app) as client:
        prefix = f"/api/collection/jobs/{job_id}"
        response = client.get(prefix + "/visualization")
        assert response.status_code == 200, response.text
        index = response.json()
        assert index["cameras"] == ["front", "wrist"]
        assert index["camera_projection_version"] == 2
        assert len(index["episodes"]) == 2
        assert index["episodes"][1]["seed"] == 43
        assert "path" not in index["episodes"][1]["videos"]["front"]
        signals = client.get(prefix + "/episodes/1/signals").json()
        with np.load(root / "trajectories/episode_000001.npz") as trace:
            np.testing.assert_allclose(
                signals["state"], trace["qpos"][trace["sample_steps"]]
            )
            np.testing.assert_allclose(
                signals["action"], trace["control"][trace["sample_steps"]]
            )
        url = index["episodes"][1]["videos"]["front"]["url"]
        video = client.get(url, headers={"Range": "bytes=0-63"})
        assert video.status_code == 206 and len(video.content) == 64
        assert "video/mp4" in video.headers["content-type"]
        assert client.get(prefix + "/episodes/1/video/main").status_code == 404
        assert client.get(prefix + "/episodes/900/signals").status_code == 404
        status = json.loads((directory / "status.json").read_text())
        status["verified"] = False
        (directory / "status.json").write_text(json.dumps(status))
        assert client.get(prefix + "/visualization").status_code == 409


def test_old_shared_video_shards_keep_episode_offsets(tmp_path):
    from backend.collection_jobs import RUNTIME

    if not RUNTIME.exists():
        pytest.skip("Collection runtime not installed")
    script = """
import sys
from pathlib import Path
import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.configs.video import RGBEncoderConfig
from backend.collection_schema import CollectionConfig
from backend.collection_data import features, EpisodeRecorder, atomic_json, JOINTS
from backend.collection_validate import verify_dataset
from backend.collection_visualization import build_index
from backend.simulation import Simulation
root = Path(sys.argv[1]) / "dataset"
config = CollectionConfig(cameras=["front"], fps=10)
dataset = LeRobotDataset.create(repo_id="local/legacy", root=root, fps=10, robot_type="so101_mujoco", features=features(32, 24, JOINTS, config.cameras), use_videos=True, video_backend="pyav", rgb_encoder=RGBEncoderConfig(vcodec="h264", pix_fmt="yuv420p", g=10), encoder_threads=1, metadata_buffer_size=1)
class Renderer:
    def capture(self, view):
        return np.full((24, 32, 3), 50 + episode * 100, dtype=np.uint8)
for episode in range(2):
    recorder = EpisodeRecorder(dataset, Renderer(), config)
    Simulation().step(200, before_step=recorder.before_step)
    dataset.save_episode(parallel_encoding=False)
    recorder.save_trace(root / f"trajectories/episode_{episode:06}.npz")
dataset.finalize()
atomic_json(root / "meta/collection.json", {"repo_id":"local/legacy", "config":config.model_dump(), "cameras":["front"], "attempts":[{"dataset_episode_index":i,"seed":i,"outcome":"succeeded","success":True} for i in range(2)]})
verify_dataset(root)
index = build_index(root)
assert index["episodes"][0]["videos"]["front"]["path"] == index["episodes"][1]["videos"]["front"]["path"]
assert abs(index["episodes"][1]["videos"]["front"]["start"] - 0.2) < 1e-6
assert index["episodes"][1]["frames"] == 2
"""
    result = subprocess.run(
        [str(RUNTIME), "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr[-4000:]


def test_visualization_paths_cannot_escape_dataset(tmp_path):
    from backend.collection_visualization import contained_file

    root = tmp_path / "dataset"
    root.mkdir()
    secret = tmp_path / "outside.mp4"
    secret.write_bytes(b"outside")
    (root / "linked.mp4").symlink_to(secret)
    for relative in ("../outside.mp4", "linked.mp4", str(secret)):
        with pytest.raises(ValueError, match="outside"):
            contained_file(root, relative)
