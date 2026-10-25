import pytest
from backend.sessions import Session, Command
from backend.tests.connection_fixture import linked


def test_simulation_run_does_not_enable_connected_hardware(linked):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    assert session.sim.running
    assert not service.enabled and service.driver.writes == []


def test_real_run_requires_successful_simulation(linked):
    service, _ = linked
    scene = Session()
    scene.id = "one"
    with pytest.raises(ValueError, match="successful simulation"):
        service.scene_command(scene, Command(type="real_run"))
    assert not service.enabled and service.driver.writes == []


def test_edit_invalidates_successful_trial():
    s = Session()
    s.successful_trial = object()
    s.invalidate_plan()
    assert s.successful_trial is None


@pytest.mark.parametrize("interruption", ["lease", "stop", "edit"])
def test_real_preparation_cancellation_never_writes_hardware(
    linked, monkeypatch, interruption
):
    service, _ = linked
    scene = Session()
    scene.id = "one"
    scene.successful_trial = scene.sim

    def rehearse(trial, cancel):
        if interruption == "lease":
            service.lease_until = 0
        elif interruption == "stop":
            service.stop("one")
        else:
            scene.invalidate_plan()
        return {"verified": True}

    monkeypatch.setattr("backend.planning.calculate_plan", rehearse)
    with pytest.raises(ValueError, match="cancelled"):
        service.run_real(scene)
    assert not service._preparing
    assert not service.enabled and service.driver.writes == []


def test_real_run_consumes_approval_and_rehearses_from_measured_pose(
    linked, monkeypatch
):
    service, _ = linked
    scene = Session()
    scene.id = "one"
    initial = scene.sim
    scene.successful_trial = initial
    observed = []

    def rehearse(trial, cancel):
        observed.append(trial)
        assert list(trial.data.qpos[:6]) == [0] * 6
        return {"verified": True, "configuration": {}}

    def start(session, trial, waypoints):
        assert session.successful_trial is None
        assert session.sim is initial and trial is observed[0]
        assert waypoints == []
        return session.packet()

    monkeypatch.setattr("backend.planning.calculate_plan", rehearse)
    monkeypatch.setattr(service.execution, "start", start)
    service.run_real(scene)
    assert not service._preparing


@pytest.mark.parametrize("worker_tick", [True, False])
def test_expired_preparation_cannot_be_revived_by_heartbeat(
    linked, monkeypatch, worker_tick
):
    service, _ = linked
    scene = Session()
    scene.id = "one"
    scene.successful_trial = scene.sim

    def rehearse(trial, cancel):
        service.lease_until = 0
        if worker_tick:
            service.tick()
        try:
            service.heartbeat("one")
        except ValueError:
            pass
        assert cancel.is_set()
        return {"verified": True}

    monkeypatch.setattr("backend.planning.calculate_plan", rehearse)
    with pytest.raises(ValueError, match="cancelled"):
        service.run_real(scene)
    assert service.driver.writes == []


@pytest.mark.parametrize("action", ["enable", "align", "sync", "calibration"])
def test_manual_controls_cannot_change_robot_during_real_preparation(
    linked, monkeypatch, action
):
    service, _ = linked
    scene = Session()
    scene.id = "one"
    scene.successful_trial = scene.sim

    def rehearse(trial, cancel):
        with pytest.raises(ValueError, match="preparation"):
            if action == "sync":
                service.sync("one", "real_to_gym")
            elif action == "calibration":
                service.save_calibration(service.calibration)
            else:
                getattr(service, action)("one")
        cancel.set()
        return {"verified": True}

    monkeypatch.setattr("backend.planning.calculate_plan", rehearse)
    with pytest.raises(ValueError, match="cancelled"):
        service.run_real(scene)
    assert service.driver.writes == []


def test_real_preflight_uses_approved_start_objects_not_finished_gym(
    linked, monkeypatch
):
    service, _ = linked
    scene = Session()
    scene.id = "one"
    scene.successful_trial = scene.sim

    def wrong_world(*_):
        raise AssertionError("Used finished Gym collision world")

    monkeypatch.setattr(service.bridge, "validate", wrong_world)
    monkeypatch.setattr(
        "backend.planning.calculate_plan", lambda *_: {"verified": True}
    )
    monkeypatch.setattr(service.execution, "start", lambda *_: scene.packet())
    service.run_real(scene)
