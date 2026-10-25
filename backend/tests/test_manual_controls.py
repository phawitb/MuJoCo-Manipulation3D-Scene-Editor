"""Manual hardware lifecycle, tested against real MuJoCo geometry and fake bus."""

import threading
from types import SimpleNamespace
import numpy as np
import pytest
from backend.tests.test_connection import Driver, calibrated
from backend.modules.connection.service import ConnectionService
from backend.modules.connection.bridge import GymBridge
from backend.simulation import Simulation
from backend.tests.test_manual_guard import Q


class Bus(Driver):
    powered = True

    def read(self):
        return [dict(row, torque=self.powered) for row in super().read()]

    def torque(self, speeds=None):
        super().torque(speeds)
        self.powered = True

    def torque_off(self):
        self.writes.append(("torque", False))
        self.powered = False


@pytest.fixture
def control(tmp_path):
    session = SimpleNamespace(sim=Simulation(), lock=threading.RLock(), closed=False)
    registry = SimpleNamespace(get=lambda _: session)
    s = ConnectionService(
        settings_dir=tmp_path,
        driver_factory=Bus,
        bridge_factory=lambda _, sid: GymBridge(registry, sid),
        start_worker=False,
    )
    calibrated(s)
    pose = list(Q)
    pose[2] -= 0.005
    s.driver.raw = s._raw(pose)
    session.sim.data.qpos[:6] = s._read()
    yield s, session
    s.shutdown()


def test_latest_target_replaces_without_extra_hardware_enable(control):
    s, session = control
    q = s._read()
    a = q.copy()
    a[4] += 0.02
    s.move("one", a)
    active = s.manual
    b = q.copy()
    b[4] += 0.04
    s.move("one", b)
    assert s.manual is active and s.manual.target == b
    assert sum(w[0] == "torque" for w in s.driver.writes) == 1
    assert np.allclose(session.sim.data.qpos[:6], q)


def test_home_uses_saved_scene_pose_and_torque_off_cancels(control):
    s, session = control
    q = s._read()
    q[4] += 0.03
    session.sim.scene.robot.reset_joints = q
    s.move("one", preset="home")
    assert s.manual.target == q
    s.torque_control("one", False)
    assert s.manual is None and not s.enabled and not s.driver.powered
    before = list(s.driver.writes)
    s.tick()
    assert s.driver.writes == before
    with pytest.raises(ValueError, match="Torque On"):
        s.move("one", q)
    s.torque_control("one", True)
    assert s.driver.writes[-2][0] == "goals"
    assert s.driver.writes[-1] == ("torque", True)
    assert s.manual is None and not s.enabled


def test_rejected_replacement_stops_previous_motion(control):
    s, _ = control
    q = s._read()
    q[4] += 0.02
    s.move("one", q)
    q[1] = 10
    with pytest.raises(Exception, match="limit"):
        s.move("one", q)
    assert s.manual is None and not s.enabled


@pytest.mark.parametrize("reason", ["lease", "scene"])
def test_manual_motion_stops_on_lost_lease_or_scene_change(control, reason):
    s, session = control
    q = s._read()
    q[4] += 0.03
    s.move("one", q)
    if reason == "lease":
        s.lease_until = 0
    else:
        session.closed = True
    s.tick()
    assert s.manual is None and not s.enabled and s.fault


def test_measured_preview_is_read_only_and_disconnected_status_works(control):
    s, session = control
    before = session.sim.data.qpos.copy()
    preview = s.status()["robot_preview"]
    assert len(preview["points"]) == 7 and len(preview["fingers"]) == 2
    assert np.array_equal(before, session.sim.data.qpos)
    s.disconnect("one")
    assert s.status()["robot_preview"] is None


def test_delayed_slider_request_cannot_restart_after_stop(control):
    s, _ = control
    epoch = s.control_epoch
    q = s._read()
    q[4] += 0.03
    s.move("one", q, control_epoch=epoch)
    s.stop("one")
    before = list(s.driver.writes)
    with pytest.raises(ValueError, match="expired"):
        s.move("one", q, control_epoch=epoch)
    assert s.driver.writes == before and s.manual is None
    s.move("one", q, control_epoch=s.control_epoch)
    assert s.manual is not None


def test_slow_path_validation_never_writes_stale_goal(control, monkeypatch):
    from backend.modules.connection.manual import MotionGuard

    s, _ = control
    q = s._read()
    q[4] += 0.03
    original = MotionGuard.path

    def slow(guard, start, end):
        original(guard, start, end)
        s.measured_at -= 1

    monkeypatch.setattr(MotionGuard, "path", slow)
    before = list(s.driver.writes)
    with pytest.raises(ValueError, match="Stale feedback"):
        s.move("one", q)
    assert s.driver.writes == before and s.manual is None


@pytest.mark.parametrize("endpoint", ["home", "match-gym"])
def test_preset_api_requires_current_control_epoch(control, endpoint):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.modules.connection.routes import create_router

    s, session = control
    q = s._read()
    session.sim.scene.robot.reset_joints = q
    app = FastAPI()
    app.include_router(create_router(s))
    client = TestClient(app)
    before = list(s.driver.writes)
    response = client.post("/api/connection/" + endpoint, json={"session_id": "one"})
    assert response.status_code == 422
    assert s.driver.writes == before
    epoch = s.control_epoch
    s.stop("one")
    before = list(s.driver.writes)
    response = client.post(
        "/api/connection/" + endpoint,
        json={"session_id": "one", "control_epoch": epoch},
    )
    assert response.status_code == 422 and s.driver.writes == before


def test_manual_tuning_does_not_leak_to_sync(control, monkeypatch):
    from backend.modules.connection.tracking import TrackingController

    s, _ = control
    q = s._read()
    q[4] += 0.03
    s.move("one", q)
    s.stop("one")
    monkeypatch.setattr(s.bridge, "validate", lambda *_: None)
    s.enable("one")
    assert s.tracker.MAX_SPEED == TrackingController.MAX_SPEED
    assert s.tracker.REFERENCE_SPEED == TrackingController.REFERENCE_SPEED
    assert s.tracker.MAX_ACCELERATION == TrackingController.MAX_ACCELERATION


def test_step_cancels_manual_before_world_changes(control):
    s, session = control
    q = s._read()
    q[4] += 0.03
    s.move("one", q)
    session.id = "one"
    session.execute = lambda _: None
    s.scene_command(session, SimpleNamespace(type="step"))
    assert s.manual is None and not s.enabled


def test_manual_start_preserves_valid_existing_servo_hold(control, monkeypatch):
    s, _ = control
    q = s._read()
    target = q.copy()
    target[4] += 0.03
    original = s.driver.read
    held_raw = list(s.driver.raw)
    held_raw[4] += 3
    monkeypatch.setattr(
        s.driver,
        "read",
        lambda: [dict(r, goal_raw=v) for r, v in zip(original(), held_raw)],
    )
    s.move("one", target)
    assert s.driver.writes[0] == ("goals", held_raw)
    assert s.tracker.bias[4] > 0


def test_reference_stays_on_validated_joint_line(control, monkeypatch):
    from backend.modules.connection.manual import ManualMotion

    s, session = control
    q = s._read()
    target = q.copy()
    target[0] += 0.03
    target[4] += 0.09
    motion = ManualMotion(s, session, q, target)
    motion.last -= 0.1
    motion.tick(q)
    delta = np.array(motion.tracker.reference) - q
    assert delta[0] / 0.03 == pytest.approx(delta[4] / 0.09)


def test_torque_on_holds_exact_encoder_outside_calibration_without_motion(control):
    s, _ = control
    s.driver.powered = False
    c = s.calibration.joints[1]
    c.raw_min = 858
    c.zero_raw = 1990.5
    s.driver.raw[1] = 850
    original_raw = list(s.driver.raw)
    original_calibration = s.calibration.model_dump()
    s.driver.writes.clear()
    result = s.torque_control("one", True)
    assert s.driver.writes[0] == ("goals", original_raw)
    assert s.driver.writes[1] == ("torque", True)
    assert s.driver.raw == original_raw
    assert not result["enabled"] and result["sync_mode"] == "off"
    assert s.manual is None
    assert s.calibration.model_dump() == original_calibration
    assert any(v["name"] == "shoulder_lift" for v in result["limit_violations"])
    before = list(s.driver.writes)
    with pytest.raises(ValueError, match=r"shoulder_lift.*850.*858"):
        s.move("one", preset="home")
    assert s.driver.writes == before


@pytest.mark.parametrize("raw", [-1, 4096, float("nan"), 850.5])
def test_torque_on_rejects_invalid_raw_measurement_before_any_write(control, raw):
    s, _ = control
    s.driver.powered = False
    s.driver.raw[1] = raw
    s.driver.writes.clear()
    with pytest.raises(ValueError, match="encoder"):
        s.torque_control("one", True)
    assert s.driver.writes == []
    assert not s.driver.powered


def test_collision_guard_checks_exact_quantized_command(control, monkeypatch):
    s,session=control
    q=s._read();q[4]+=.03
    s.move('one',q)
    checked=[]
    original=s.manual.guard.path
    def observe(start,end):
        checked.append(list(end));return original(start,end)
    monkeypatch.setattr(s.manual.guard,'path',observe)
    s.manual.last-=.1;s.tick()
    sent=[w[1] for w in s.driver.writes if w[0]=='goals'][-1]
    exact=[s._angle(i,raw) for i,raw in enumerate(sent)]
    assert any(np.array_equal(end,exact) for end in checked)
