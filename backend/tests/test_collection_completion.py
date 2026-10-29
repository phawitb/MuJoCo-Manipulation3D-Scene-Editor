import json
import numpy as np
import pytest
from backend.collection_schema import CollectionConfig, Variation
from backend.collection_randomization import episode_scene
from backend.examples import example_scene


def test_new_defaults_and_legacy_explicit_settings():
    fresh = CollectionConfig()
    assert fresh.variation.position_mode == "workspace"
    assert fresh.duration_mode == "auto"
    assert fresh.max_attempts == 250
    assert not fresh.include_failed
    old = CollectionConfig.model_validate(
        {"max_seconds": 1, "variation": {"position_radius": 0.02}}
    )
    assert old.duration_mode == "fixed"
    assert old.variation.position_mode == "radius"
    assert old.max_attempts == 25
    assert Variation(position_mode="radius", position_radius=0.4).position_radius == 0.4
    with pytest.raises(ValueError):
        Variation(position_radius=0.41)


def test_workspace_samples_broadly_and_preserves_contained_footprints():
    from backend.collection_positions import object_half_extent

    source = example_scene("kalas-loaded-cup-to-plate")
    config = Variation(position_mode="workspace")
    originals = {o.id: np.array(o.position) for o in source.objects}
    shifts = []
    for seed in range(30):
        moved = episode_scene(source, config, seed)
        assert moved == episode_scene(source, config, seed)
        current = {o.id: np.array(o.position) for o in moved.objects}
        np.testing.assert_allclose(
            current["cup"] - originals["cup"],
            current["spoon"] - originals["spoon"],
            atol=1e-12,
        )
        shifts.append(np.linalg.norm(current["cup"][:2] - originals["cup"][:2]))
        for obj in moved.objects:
            assert np.all(
                np.abs(obj.position[:2]) + object_half_extent(obj)[:2]
                <= np.array([moved.table.width, moved.table.depth]) / 2 - 0.005
            )
            assert obj.position[2] == originals[obj.id][2]
            assert obj.quaternion == next(
                o.quaternion for o in source.objects if o.id == obj.id
            )
    assert max(shifts) > 0.15
    assert sum(s > 0.05 for s in shifts) > 20
    assert source == example_scene("kalas-loaded-cup-to-plate")


def test_capture_limit_uses_rehearsal_and_rejects_short_success_only_limits():
    from backend.collection_worker import capture_time_limit

    assert (
        capture_time_limit(
            CollectionConfig(duration_mode="auto", max_seconds=1), {"duration": 29.9}
        )
        >= 39
    )
    with pytest.raises(ValueError, match="shorter than.*rehearsal"):
        capture_time_limit(
            CollectionConfig(duration_mode="fixed", max_seconds=1), {"duration": 17.9}
        )
    assert (
        capture_time_limit(
            CollectionConfig(duration_mode="fixed", max_seconds=1, include_failed=True),
            {"duration": 17.9},
        )
        == 1
    )


def test_legacy_job_reports_task_success_separately_from_format(tmp_path, monkeypatch):
    from backend.collection_jobs import CollectionJobs

    monkeypatch.setenv("SO101_RECORDINGS_DIR", str(tmp_path))
    job_id = "a" * 32
    folder = tmp_path / job_id
    (folder / "dataset/meta").mkdir(parents=True)
    (folder / "config.json").write_text("{}")
    (folder / "status.json").write_text(
        json.dumps({"status": "completed", "verified": True, "saved_episodes": 2})
    )
    (folder / "dataset/meta/collection.json").write_text(
        json.dumps(
            {
                "attempts": [
                    {
                        "dataset_episode_index": None,
                        "success": False,
                        "outcome": "rejected",
                    },
                    {
                        "dataset_episode_index": 0,
                        "success": True,
                        "outcome": "succeeded",
                    },
                    {
                        "dataset_episode_index": 1,
                        "success": False,
                        "outcome": "timeout",
                    },
                ]
            }
        )
    )
    status = CollectionJobs().get(job_id)
    assert status["download_available"]
    assert status["successful_episodes"] == 1
    assert status["unsuccessful_episodes"] == 1


def test_real_workspace_capture_finishes_two_tasks_with_automatic_duration(tmp_path):
    import subprocess
    from pathlib import Path

    runtime = Path(__file__).resolve().parents[2] / ".venv-collect/bin/python"
    if not runtime.exists():
        pytest.skip("Collection runtime not installed")
    source = example_scene("kalas-cup-front")
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "id": "workspace-integration",
                "scene": source.model_dump(),
                "config": {
                    "episodes": 2,
                    "seed": 42,
                    "cameras": ["front", "wrist"],
                    "fps": 10,
                    "resolution": "320x240",
                    "duration_mode": "auto",
                    "max_seconds": 1,
                    "variation": {"position_mode": "workspace"},
                },
            }
        )
    )
    result = subprocess.run(
        [str(runtime), "-m", "backend.collection_worker", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["verified"] and status["successful_episodes"] == 2
    assert status["unsuccessful_episodes"] == 0
    attempts = json.loads((tmp_path / "dataset/meta/collection.json").read_text())[
        "attempts"
    ]
    kept = [a for a in attempts if a["dataset_episode_index"] is not None]
    assert len(kept) == 2
    assert any(a["outcome"] == "rejected" for a in attempts)
    for entry in kept:
        assert entry["success"] and entry["outcome"] == "succeeded"
        assert entry["terminal_time"] > 15
        assert entry["capture_time_limit"] > entry["terminal_time"]
        assert entry["frames"] > 150
        assert any(
            np.linalg.norm(np.array(o["position"][:2]) - orig.position[:2]) > 0.05
            for o, orig in zip(entry["scene"]["objects"], source.objects)
        )
        trace = np.load(
            tmp_path
            / f"dataset/trajectories/episode_{entry['dataset_episode_index']:06}.npz"
        )
        assert (
            trace["time"][trace["sample_steps"][-1]] >= entry["terminal_time"] - 0.101
        )
    assert kept[0]["scene"]["objects"] != kept[1]["scene"]["objects"]
