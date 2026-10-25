import math
import pytest
from backend.modules.connection.episode_report import EpisodeReport


def test_endpoint_report_distinguishes_arrival_from_physical_task_success():
    report = EpisodeReport("scene")
    report.observe(dict(position_mm=10, orientation_deg=2, opening_deg=1))
    report.observe(dict(position_mm=2, orientation_deg=0.5, opening_deg=0.1))
    result = report.finish("completed", "Tool goals reached")
    assert result["samples"] == 2 and result["last_error"]["position_mm"] == 2
    assert result["peak_target_distance_mm"] == 10
    assert result["rms_target_distance_mm"] == pytest.approx(math.sqrt(52))
    assert result["measurement_source"] == "encoder_fk"
    assert result["environment_source"] == "simulation_rehearsal"
    assert result["object_verified"] is False
    assert "joints" not in result


def test_stopped_report_never_invents_measurements():
    result = EpisodeReport("scene").finish("stopped", "Feedback lost")
    assert result["outcome"] == "stopped" and result["samples"] == 0
    assert result["last_error"] is None and result["last_sample_age_s"] is None
    assert result["object_verified"] is False


def test_invalid_errors_do_not_pollute_report():
    report = EpisodeReport("scene")
    with pytest.raises(ValueError):
        report.observe(dict(position_mm=math.nan, orientation_deg=0, opening_deg=0))
    assert report.count == 0
