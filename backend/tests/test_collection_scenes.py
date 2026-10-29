import numpy as np
from backend.examples import example_scene
from backend.collection_schema import CollectionConfig, Variation
from backend.collection_randomization import episode_scene


def test_all_defaults_except_robot():
    from backend.collection_schema import ALL_COLORS, ALL_PATTERNS, ALL_ENVIRONMENTS

    config = CollectionConfig()
    assert config.variation.robot_colors == ["#f1792e", "#ffd11f"]
    for key in ("table", "motor", "leg", "floor", "wall", "background", "object"):
        assert getattr(config.variation, key + "_colors") == ALL_COLORS
    for key in ("robot", "table", "floor", "wall"):
        assert getattr(config.variation, key + "_patterns") == ALL_PATTERNS
    assert config.variation.environments == ALL_ENVIRONMENTS
    assert config.variation.lighting and config.variation.finishes
    assert config.variation.positions


def test_scene_selection_is_independent_of_live_task():
    from backend.collection_scenes import collection_scene
    from backend.schema import Scene

    original = Scene()
    original.appearance.robot_color = "#ff6600"
    selected = collection_scene(original, "kalas-cup-front")
    assert selected.task.source == "spoon" and selected.task.target == "cup"
    assert selected.name == "01 · Spoon into cup"
    assert selected.appearance == original.appearance
    assert not original.objects


def test_positions_move_both_objects_reproducibly_without_other_physics_changes():
    source = example_scene("kalas-cup-front")
    config = Variation(positions=True, position_radius=0.02)
    first = episode_scene(source, config, 42)
    assert first == episode_scene(source, config, 42)
    other = episode_scene(source, config, 43)
    for before, after, different in zip(source.objects, first.objects, other.objects):
        assert after.position[:2] != before.position[:2]
        assert after.position[:2] != different.position[:2]
        assert (
            np.linalg.norm(np.array(after.position[:2]) - before.position[:2]) <= 0.02
        )
        assert after.position[2] == before.position[2]
        assert after.quaternion == before.quaternion
        assert after.mass == before.mass
    locked = episode_scene(source, config.model_copy(update={"positions": False}), 42)
    assert [o.position for o in locked.objects] == [o.position for o in source.objects]


def test_contained_objects_move_with_their_support():
    for scene_id, ids in [
        ("kalas-cup-to-plate", ("spoon", "source_cup")),
        ("kalas-loaded-cup-to-plate", ("cup", "spoon")),
    ]:
        source = example_scene(scene_id)
        result = episode_scene(source, Variation(), 42)
        before = {o.id: np.array(o.position) for o in source.objects}
        after = {o.id: np.array(o.position) for o in result.objects}
        assert not np.allclose(after[ids[0]], before[ids[0]])
        np.testing.assert_allclose(
            after[ids[0]] - before[ids[0]], after[ids[1]] - before[ids[1]], atol=1e-12
        )


def test_scene_api_can_select_example_from_empty_editor(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app

    monkeypatch.setenv("SO101_RECORDINGS_DIR", str(tmp_path))
    with TestClient(app) as client:
        original = client.post("/api/sessions").json()
        seen = []
        monkeypatch.setattr(
            app.state.collection,
            "start",
            lambda scene, config, sid: (
                seen.append(scene) or {"scene_id": config.scene_id}
            ),
        )
        sid = original["sessionId"]
        result = client.post(
            f"/api/sessions/{sid}/collection", json={"scene_id": "kalas-cup-front"}
        )
        assert result.status_code == 200
        assert seen[0].task.source == "spoon"
        assert seen[0].task.target == "cup"
        assert client.get(f"/api/sessions/{sid}").json()["scene"] == original["scene"]
        assert (
            client.post(
                f"/api/sessions/{sid}/collection", json={"scene_id": "bad"}
            ).status_code
            == 422
        )


def test_retry_replans_each_seed_and_collects_requested_count(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest

    runtime = Path(__file__).resolve().parents[2] / ".venv-collect/bin/python"
    if not runtime.exists():
        pytest.skip("Collection runtime not installed")
    source = example_scene("kalas-cup-front")
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "id": "retries",
                "scene": source.model_dump(),
                "config": {
                    "scene_id": "kalas-cup-front",
                    "episodes": 2,
                    "fps": 10,
                    "resolution": "320x240",
                    "max_seconds": 30,
                    "variation": {"position_mode": "radius"},
                },
            }
        )
    )
    script = """
import sys
import backend.planning as planning
from backend.collection_worker import collect
original = planning.calculate_plan
count = 0
def reject_first(sim, cancel):
    global count
    count += 1
    if count == 1:
        return {"verified": False, "message": "Injected placement rejection"}
    return original(sim, cancel)
planning.calculate_plan = reject_first
sys.exit(collect(sys.argv[1]))
"""
    result = subprocess.run(
        [str(runtime), "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["saved_episodes"] == 2 and status["verified"]
    manifest = json.loads((tmp_path / "dataset/meta/collection.json").read_text())
    assert manifest["attempts"][0]["outcome"] == "rejected"
    saved = [
        entry
        for entry in manifest["attempts"]
        if entry["dataset_episode_index"] is not None
    ]
    assert len(saved) == 2 and all(entry["success"] for entry in saved)
    assert (
        saved[0]["scene"]["objects"][0]["position"]
        != saved[1]["scene"]["objects"][0]["position"]
    )
    assert (
        saved[0]["scene"]["objects"][1]["position"]
        != saved[1]["scene"]["objects"][1]["position"]
    )
    assert all("controller_configuration" in entry for entry in saved)


def test_cargo_below_container_center_and_spoon_tip_move_with_container():
    from backend.schema import SceneObject

    source = example_scene("kalas-rim-to-plate")
    source.objects.append(
        SceneObject(
            id="cargo", asset="cube", scale=0.25, position=[-0.08, -0.07, 0.758]
        )
    )
    # Its center is outside; one end extends into the vessel.
    source.objects.append(
        SceneObject(id="spoon", asset="kalas_spoon", position=[-0.14, -0.07, 0.80])
    )
    result = episode_scene(source, Variation(), 42)
    before = {o.id: np.array(o.position) for o in source.objects}
    after = {o.id: np.array(o.position) for o in result.objects}
    cup_shift = after["cup"] - before["cup"]
    assert not np.allclose(cup_shift, 0)
    for oid in ("cargo", "spoon"):
        np.testing.assert_allclose(after[oid] - before[oid], cup_shift, atol=1e-12)


def test_positions_stay_on_table_and_reject_impossible_footprint():
    import pytest
    from backend.collection_positions import object_half_extent

    source = example_scene("kalas-cup-front")
    for seed in range(20):
        moved = episode_scene(source, Variation(position_radius=0.05), seed)
        for obj in moved.objects:
            assert np.all(
                np.abs(obj.position[:2]) + object_half_extent(obj)[:2]
                <= np.array([moved.table.width, moved.table.depth]) / 2 - 0.005
            )
    source.objects[0].position[0] = source.table.width / 2
    with pytest.raises(ValueError, match="fits the table"):
        episode_scene(source, Variation(position_radius=0.01), 42)


def test_rejected_placements_stop_at_budget_and_never_claim_requested_count(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest

    runtime = Path(__file__).resolve().parents[2] / ".venv-collect/bin/python"
    if not runtime.exists():
        pytest.skip("Collection runtime not installed")
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "id": "rejected",
                "scene": example_scene("kalas-cup-front").model_dump(),
                "config": {
                    "episodes": 1,
                    "fps": 10,
                    "resolution": "320x240",
                    "variation": {"position_mode": "radius"},
                },
            }
        )
    )
    script = """
import sys
import backend.planning as planning
from backend.collection_worker import collect
planning.calculate_plan = lambda sim, cancel: {"verified": False, "message": "Unreachable test placement"}
sys.exit(collect(sys.argv[1]))
"""
    result = subprocess.run(
        [str(runtime), "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1, result.stderr[-2000:]
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["saved_episodes"] == 0 and status["status"] == "failed"
    assert "0/1" in status["message"] and "5 attempts" in status["message"]
    manifest = json.loads((tmp_path / "dataset/meta/collection.json").read_text())
    assert [a["seed"] for a in manifest["attempts"]] == list(range(42, 47))
    assert all(
        a["outcome"] == "rejected" and a["dataset_episode_index"] is None
        for a in manifest["attempts"]
    )
