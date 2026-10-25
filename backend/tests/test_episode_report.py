import math
import pytest
from backend.modules.connection.episode_report import EpisodeReport


def test_reports_all_sample_errors_and_distinguishes_final_error():
    report = EpisodeReport('scene')
    report.observe([0.1] * 6, [0] * 6, 0)
    report.observe([0.02] * 6, [0] * 6, 1)
    result = report.finish('completed', 'Reached final pose')
    assert result['samples'] == 2 and result['outcome'] == 'completed'
    joint = result['joints'][0]
    assert joint['max_abs_error_deg'] == pytest.approx(math.degrees(0.1))
    assert joint['rmse_deg'] == pytest.approx(math.degrees(math.sqrt(0.0052)))
    assert joint['last_error_deg'] == pytest.approx(math.degrees(0.02))
    assert result['simulation_time_s'] == 1


def test_stopped_report_does_not_claim_completion_or_invent_feedback():
    report = EpisodeReport('scene')
    result = report.finish('stopped', 'Feedback lost')
    assert result['outcome'] == 'stopped'
    assert result['samples'] == 0 and result['joints'] == []
    assert result['last_sample_age_s'] is None


def test_invalid_measurements_do_not_pollute_report():
    report = EpisodeReport('scene')
    with pytest.raises(ValueError):
        report.observe([math.nan] * 6, [0] * 6, 0)
    assert report.finish('stopped', 'Bad feedback')['samples'] == 0
