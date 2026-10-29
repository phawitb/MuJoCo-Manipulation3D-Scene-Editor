import importlib.util
from pathlib import Path

import numpy as np
import pytest
from backend.schema import Scene
from backend.simulation import Simulation


def test_collection_palettes_are_bounded_independent_and_reproducible():
    assert importlib.util.find_spec("backend.collection_schema"), (
        "Collection configuration is not implemented"
    )
    from backend.collection_schema import CollectionConfig, Variation
    from backend.collection_randomization import episode_scene

    original = Scene()
    config = Variation(
        robot_colors=["#ff8800", "#ffff00"],
        table_colors=["#ffffff", "#808080", "#000000"],
    )
    results = [episode_scene(original, config, seed) for seed in range(20)]
    assert {s.appearance.robot_color for s in results} == {"#ff8800", "#ffff00"}
    assert {s.table.color for s in results} == {"#ffffff", "#808080", "#000000"}
    for seed, scene in enumerate(results):
        assert scene.model_dump() == episode_scene(original, config, seed).model_dump()
        assert scene.robot == original.robot
        assert scene.objects == original.objects
        assert scene.appearance.robot.pattern == original.appearance.robot.pattern
        assert scene.appearance.robot.secondary in config.robot_colors
        assert scene.appearance.motor_color == original.appearance.motor_color
        other = config.model_copy(
            update={"table_colors": ["#000000"], "lighting": True}
        )
        assert (
            episode_scene(original, other, seed).appearance.robot_color
            == scene.appearance.robot_color
        )
    for value in [
        {"robot_colors": ["orange"]},
        {"robot_patterns": ["bad"]},
        {"environments": ["bad"]},
        {"repeat_min": 12, "repeat_max": 2},
    ]:
        with pytest.raises(ValueError):
            Variation.model_validate(value)
    for value in [
        {"episodes": 0},
        {"fps": 30},
        {"name": "../escape"},
        {"seed": 2147483647, "episodes": 2},
    ]:
        with pytest.raises(ValueError):
            CollectionConfig.model_validate(value)


def test_before_step_hook_records_exact_observation_and_applied_control():
    sim = Simulation()
    seen = []

    def observe(s):
        seen.append((float(s.data.time), s.data.qpos.copy(), s.data.ctrl.copy()))

    sim.step(5, before_step=observe)
    assert [round(x[0], 6) for x in seen] == [0, 0.001, 0.002, 0.003, 0.004]
    np.testing.assert_array_equal(seen[0][1], Scene().robot.joints)
    assert sim.data.time == 0.005


def test_real_worker_exports_readable_synchronized_lerobot(tmp_path):
    import json
    import subprocess
    from backend.examples import example_scene

    runtime = Path(__file__).resolve().parents[2] / ".venv-collect/bin/python"
    if not runtime.exists():
        pytest.skip(
            "Run scripts/setup-collection.sh for the real LeRobot integration test"
        )
    config = {
        "id": "integration",
        "scene": example_scene().model_dump(),
        "config": {
            "name": "test-collection",
            "episodes": 2,
            "fps": 10,
            "resolution": "320x240",
            "max_seconds": 1,
            "include_failed": True,
        },
    }
    (tmp_path / "config.json").write_text(json.dumps(config))
    result = subprocess.run(
        [str(runtime), "-m", "backend.collection_worker", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["status"] == "completed"
    assert status["saved_episodes"] == 2
    assert status["verified"] is True
    root = tmp_path / "dataset"
    verify = json.loads((root / "meta/collection-verification.json").read_text())
    assert verify["frames"] == 20
    assert verify["episodes"] == 2
    assert verify["cameras"] == ["main", "top", "front", "back", "wrist"]
    for i in range(2):
        recipe = json.loads((root / f"meta/collection/episode_{i:06}.json").read_text())
        assert recipe["seed"] == 42 + i
        assert recipe["success"] is False
        assert recipe["scene"]["appearance"]["robot_color"] in ["#f1792e", "#ffd11f"]
        trace = np.load(root / f"trajectories/episode_{i:06}.npz")
        np.testing.assert_allclose(
            trace["time"][trace["sample_steps"]], np.arange(10) / 10, atol=1e-9
        )
        assert trace["qpos"].shape == (1000, 6)
        assert trace["control"].shape == (1000, 6)


def test_collection_api_rejects_unselected_task_and_invalid_config(
    tmp_path, monkeypatch
):
    from fastapi.testclient import TestClient
    from backend.main import app

    monkeypatch.setenv("SO101_RECORDINGS_DIR", str(tmp_path))
    with TestClient(app) as c:
        capabilities = c.get("/api/collection")
        assert capabilities.status_code == 200
        assert capabilities.json()["cameras"] == [
            "main",
            "top",
            "front",
            "back",
            "wrist",
        ]
        snapshot = c.post("/api/sessions").json()
        sid = snapshot["sessionId"]
        assert (
            c.post(
                f"/api/sessions/{sid}/collection", json={"name": "../escape"}
            ).status_code
            == 422
        )
        assert c.post(f"/api/sessions/{sid}/collection", json={}).status_code == 422
        assert c.get("/api/collection/jobs/not-a-job/download").status_code == 404
        assert not list(tmp_path.iterdir())


def test_cancel_keeps_completed_episodes_and_excludes_partial(tmp_path, monkeypatch):
    import time
    from backend.collection_jobs import CollectionJobs, TERMINAL
    from backend.collection_schema import CollectionConfig
    from backend.examples import example_scene

    monkeypatch.setenv("SO101_RECORDINGS_DIR", str(tmp_path))
    manager = CollectionJobs()
    if not manager.ready():
        pytest.skip("Collection runtime not installed")
    config = CollectionConfig(
        episodes=5, fps=10, resolution="320x240", max_seconds=1, include_failed=True
    )
    try:
        job = manager.start(example_scene(), config, "test")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            status = manager.get(job["id"])
            if status["saved_episodes"] >= 1 and status["status"] == "recording":
                manager.cancel(job["id"])
                break
            assert status["status"] not in TERMINAL, status
            time.sleep(0.02)
        else:
            pytest.fail("No recording progress within deadline")
        while time.monotonic() < deadline:
            status = manager.get(job["id"])
            if status["status"] in TERMINAL:
                break
            time.sleep(0.05)
        assert status["status"] == "cancelled", status
        assert 1 <= status["saved_episodes"] < 5
        assert status["download_available"]
        import json

        manifest = json.loads(
            (manager.directory(job["id"]) / "dataset/meta/collection.json").read_text()
        )
        interrupted = manifest["attempts"][-1]
        assert interrupted["outcome"] == "cancelled"
        assert interrupted["dataset_episode_index"] is None
        assert interrupted["seed"] == config.seed + status["episode"] - 1
        archive, name = manager.archive(job["id"])
        assert archive.is_file()
        assert name.endswith("-lerobot.zip")
    finally:
        manager.close()


def test_palette_constrains_existing_pattern_secondary_without_changing_pattern():
    from backend.collection_schema import Variation
    from backend.collection_randomization import episode_scene

    source = Scene()
    source.appearance.robot.pattern = "checker"
    source.appearance.robot.secondary = "#0000ff"
    source.appearance.table.pattern = "stripes"
    source.appearance.table.secondary = "#ff0000"
    config = Variation()
    result = episode_scene(source, config, 42)
    assert result.appearance.robot.secondary in config.robot_colors
    assert result.appearance.table.secondary in config.table_colors
    assert result.appearance.robot.pattern == "checker"
    assert result.appearance.table.pattern == "stripes"
    changed_patterns = config.model_copy(update={"robot_patterns": ["dots"]})
    assert (
        episode_scene(source, changed_patterns, 42).appearance.robot.secondary
        == result.appearance.robot.secondary
    )


def test_encoding_failure_preserves_prior_committed_episode(tmp_path):
    import json
    import subprocess
    from backend.examples import example_scene

    runtime = Path(__file__).resolve().parents[2] / ".venv-collect/bin/python"
    if not runtime.exists():
        pytest.skip("Collection runtime not installed")
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "id": "encoding-failure",
                "scene": example_scene().model_dump(),
                "config": {
                    "episodes": 2,
                    "fps": 10,
                    "resolution": "320x240",
                    "max_seconds": 1,
                    "include_failed": True,
                },
            }
        )
    )
    script = """
import sys
from lerobot.datasets.dataset_writer import DatasetWriter
from backend.collection_worker import collect
original = DatasetWriter._save_episode_video
def failing(self, key, index, *args, **kwargs):
    if index == 1 and key.endswith("top"):
        raise RuntimeError("Injected video failure after main camera was saved")
    return original(self, key, index, *args, **kwargs)
DatasetWriter._save_episode_video = failing
sys.exit(collect(sys.argv[1]))
"""
    result = subprocess.run(
        [str(runtime), "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 1
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["saved_episodes"] == 1
    assert status["verified"] is True, result.stderr[-4000:]
    root = tmp_path / "dataset"
    verification = json.loads((root / "meta/collection-verification.json").read_text())
    assert verification["frames"] == 10
    manifest = json.loads((root / "meta/collection.json").read_text())
    assert len(manifest["attempts"]) == 2
    assert manifest["attempts"][1]["seed"] == 43
    assert manifest["attempts"][1]["dataset_episode_index"] is None
    assert manifest["attempts"][1]["outcome"] == "error"


def test_commit_restores_metadata_even_when_finalization_repeatedly_fails(tmp_path):
    from types import SimpleNamespace
    from backend.collection_commit import commit_episode

    root = tmp_path / "dataset"
    (root / "meta").mkdir(parents=True)
    (root / "meta/info.json").write_text("original")
    (root / "data").mkdir()
    (root / "data/committed.parquet").write_bytes(b"committed")

    class BrokenDataset:
        writer = SimpleNamespace(_pq_writer=None)
        meta = SimpleNamespace(_pq_writer=None)

        def save_episode(self, **kwargs):
            (root / "meta/info.json").write_text("uncommitted")
            (root / "data/partial.parquet").write_bytes(b"partial")

        def finalize(self):
            raise OSError("Cannot finalize")

    recorder = SimpleNamespace(save_trace=lambda path: None)
    with pytest.raises(OSError, match="Cannot finalize"):
        commit_episode(BrokenDataset(), recorder, {"dataset_episode_index": 1}, root)
    assert (root / "meta/info.json").read_text() == "original"
    assert (root / "data/committed.parquet").read_bytes() == b"committed"
    assert not (root / "data/partial.parquet").exists()
