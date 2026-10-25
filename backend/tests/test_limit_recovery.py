"""Small boundary recovery must remain bounded, collision-checked and stoppable."""

import threading
from types import SimpleNamespace
import pytest
from backend.schema import Scene
from backend.simulation import Simulation
from backend.modules.connection.service import ConnectionService
from backend.modules.connection.bridge import GymBridge
from backend.modules.connection.schemas import Calibration
from backend.tests.test_connection import Driver, JOINT_NAMES
from backend.modules.connection.limit_recovery import recover_limits

RAW = [2055, 901, 3108, 2896, 1040, 2035]
ZEROS = [2111.5, 1990.5, 2003.5, 2050, 2047.5, 2037]
RANGES = [(799, 3424), (858, 3123), (898, 3109), (899, 3201), (0, 4095), (2037, 3514)]


class Bus(Driver):
    def torque(self, speeds=None):
        self.writes.append(("torque", speeds))

    def position_deadbands(self):
        return [10] * 6

    def open(self):
        self.raw = RAW.copy()
        self.held = self.raw.copy()

    def read(self):
        return [
            dict(r, torque=True, goal_raw=g, moving=False, present_speed_raw=0)
            for r, g in zip(super().read(), self.held)
        ]

    def goals(self, values):
        self.writes.append(("goals", list(values)))
        self.held = list(values)
        if not getattr(self, "stalled", False):
            self.raw = list(values)


@pytest.fixture
def setup(tmp_path):
    session = SimpleNamespace(
        sim=Simulation(Scene(robot={"pedestal_height": 0.0222})),
        lock=threading.RLock(),
        closed=False,
    )
    registry = SimpleNamespace(get=lambda _: session)
    s = ConnectionService(
        settings_dir=tmp_path,
        driver_factory=Bus,
        bridge_factory=GymBridge,
        start_worker=False,
    )
    s.connect("/dev/fake", "one", registry)
    s.save_calibration(
        Calibration(
            session_id="one",
            identity=s.identity,
            confirmed=True,
            joints=[
                dict(name=n, zero_raw=z, direction=1, raw_min=r[0], raw_max=r[1])
                for n, z, r in zip(JOINT_NAMES, ZEROS, RANGES)
            ],
        )
    )
    yield s, session
    s.shutdown()


def test_recovery_moves_only_small_offending_axes_and_preserves_limits(setup):
    s, _ = setup
    before = s.calibration.model_dump()
    result = recover_limits(s, "one", s.control_epoch)
    assert s.driver.held == [2055, 901, 3094, 2896, 1040, 2049]
    assert not result["limit_violations"] and not result["enabled"]
    assert s.calibration.model_dump() == before
    assert s.sync_mode == "off" and not s.recovering


@pytest.mark.parametrize("reason", ["large", "collision", "epoch", "goal", "active"])
def test_recovery_rejections_write_nothing(setup, reason):
    s, session = setup
    epoch = s.control_epoch
    if reason == "large":
        s.driver.raw[2] += 20
        s.driver.held = s.driver.raw.copy()
    if reason == "collision":
        scene = session.sim.scene.model_copy(deep=True)
        scene.robot.pedestal_height = 0
        session.sim.load(scene)
    if reason == "epoch":
        epoch -= 1
    if reason == "goal":
        s.driver.held[1] += 30
    if reason == "active":
        s.enabled = True
    with pytest.raises(ValueError):
        recover_limits(s, "one", epoch)
    assert not s.driver.writes


@pytest.mark.parametrize(
    "reason", ["stall", "stop", "scene", "lease", "drift", "collision"]
)
def test_recovery_faults_stop_at_measured_hold(setup, monkeypatch, reason):
    from backend.modules.connection import limit_recovery as module

    s, session = setup
    s.driver.stalled = True
    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def advance(seconds):
        clock[0] += seconds
        if reason != "lease":
            s.heartbeat("one")
        if reason == "stop":
            s.stop("one")
        if reason == "scene":
            session.sim = Simulation()
        if reason == "drift":
            s.driver.raw[1] += 20
        if reason == "collision":

            def collide(*_):
                raise ValueError("collision")

            monkeypatch.setattr(module.RecoveryGuard, "observe", collide)

    monkeypatch.setattr(module.time, "sleep", advance)
    with pytest.raises(ValueError):
        recover_limits(s, "one", s.control_epoch)
    assert not s.enabled and not s.recovering
    assert s.driver.held == s.driver.raw
    assert not any(w == ("torque", False) for w in s.driver.writes)


def test_api_requires_epoch_and_recovery_invalidates_queued_commands(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.modules.connection.routes import create_router

    s, _ = setup
    app = FastAPI()
    app.include_router(create_router(s))
    client = TestClient(app)
    assert (
        client.post(
            "/api/connection/recover-limits", json={"session_id": "one"}
        ).status_code
        == 422
    )
    assert not s.driver.writes
    epoch = s.control_epoch
    response = client.post(
        "/api/connection/recover-limits",
        json={"session_id": "one", "control_epoch": epoch},
    )
    assert response.status_code == 200 and not response.json()["limit_violations"]
    before = list(s.driver.writes)
    with pytest.raises(ValueError, match="expired"):
        s.move("one", s._read(), control_epoch=epoch)
    assert s.driver.writes == before


def test_other_controllers_cannot_change_recovery_target(setup, monkeypatch):
    from backend.modules.connection import limit_recovery as module

    s, _ = setup
    calls = []

    def concurrent(_):
        for call in (
            lambda: s.jog("one", 0, 0.01),
            lambda: s.sync("one", "gym_to_real"),
            lambda: s.move("one", s._read()),
        ):
            with pytest.raises((ValueError, ConnectionError)):
                call()
            calls.append(True)

    monkeypatch.setattr(module.time, "sleep", concurrent)
    recover_limits(s, "one", s.control_epoch)
    assert calls


def test_path_retains_separation_before_later_deepening():
    from backend.modules.connection.limit_recovery import check_recovery_path

    class Guard:
        previous = {"contact": -0.004}

        def check(self, q, previous):
            # First separate 0.3 mm, then deepen 0.06 mm per half tick.
            # Each edge is smaller than tolerance but cumulative motion is not.
            depth = -0.004 if q[0] == 0 else -0.0037 - max(0, q[0] - 0.5) * 0.00012
            if depth < previous["contact"] - 0.0001:
                raise ValueError("deepening")
            return {"contact": max(previous["contact"], depth)}

    service = SimpleNamespace(_angle=lambda _, raw: raw)
    with pytest.raises(ValueError, match="deepening"):
        check_recovery_path(Guard(), service, [0] * 6, [3, 0, 0, 0, 0, 0], 0)


def test_settling_short_of_goal_replans_next_axis_from_actual_encoder(
    setup, monkeypatch
):
    s, _ = setup

    def deadband_goals(values):
        s.driver.writes.append(("goals", list(values)))
        s.driver.held = list(values)
        for i, v in enumerate(values):
            delta = v - s.driver.raw[i]
            if abs(delta) > 10:
                s.driver.raw[i] = v - (10 if delta > 0 else -10)

    monkeypatch.setattr(s.driver, "goals", deadband_goals)
    result = recover_limits(s, "one", s.control_epoch)
    assert not result["limit_violations"]
    assert s.driver.raw == [2055, 901, 3104, 2896, 1040, 2039]
    assert s.driver.held == s.driver.raw
    goals = [v for kind, v in s.driver.writes if kind == "goals"]
    assert goals[1][2] == 3094 and goals[1][5] == 2035
    assert any(v[2] == 3104 and v[5] == 2049 for v in goals)


def test_large_servo_deadband_does_not_expand_recovery_budget(setup, monkeypatch):
    s, _ = setup
    monkeypatch.setattr(s.driver, "position_deadbands", lambda: [100] * 6)
    with pytest.raises(ValueError, match="bounded recovery"):
        recover_limits(s, "one", s.control_epoch)
    assert not s.driver.writes


def test_next_axis_requires_fresh_confirmed_stationary_hold(setup, monkeypatch):
    s, _ = setup
    original_read, original_goals = s.driver.read, s.driver.goals
    reads = [0]
    held_at = [None]
    gripper_at = []

    def read():
        reads[0] += 1
        return original_read()

    def goals(values):
        if values[5] != RAW[5]:
            gripper_at.append(reads[0])
        elif values == s.driver.raw and values[2] != RAW[2]:
            held_at[0] = reads[0]
        original_goals(values)

    monkeypatch.setattr(s.driver, "read", read)
    monkeypatch.setattr(s.driver, "goals", goals)
    recover_limits(s, "one", s.control_epoch)
    assert held_at[0] is not None
    assert min(gripper_at) - held_at[0] >= 5


def test_moving_feedback_never_launches_second_axis(setup, monkeypatch):
    from backend.modules.connection import limit_recovery as module

    s, _ = setup
    read = s.driver.read
    clock = [100.0]
    monkeypatch.setattr(
        s.driver,
        "read",
        lambda: [dict(r, moving=True, present_speed_raw=10) for r in read()],
    )
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def advance(dt):
        clock[0] += dt
        s.heartbeat("one")

    monkeypatch.setattr(module.time, "sleep", advance)
    with pytest.raises(ValueError, match="did not settle"):
        recover_limits(s, "one", s.control_epoch)
    assert s.driver.raw[5] == RAW[5] and not s.enabled


def test_measured_overshoot_cannot_exceed_absolute_recovery_budget(setup, monkeypatch):
    s, _ = setup
    goals = s.driver.goals
    monkeypatch.setattr(s.driver, "position_deadbands", lambda: [13] * 6)

    def overshoot(values):
        before = s.driver.raw.copy()
        goals(values)
        for i, (a, b) in enumerate(zip(before, values)):
            if abs(a - b) > 1:
                s.driver.raw[i] += 1 if b > a else -1

    monkeypatch.setattr(s.driver, "goals", overshoot)
    with pytest.raises(ValueError, match="bounded recovery"):
        recover_limits(s, "one", s.control_epoch)
    assert not s.enabled and s.driver.held == s.driver.raw


def test_recovery_uses_slow_nonzero_profile_above_subunit_speed(setup):
    s, _ = setup
    recover_limits(s, "one", s.control_epoch)
    assert ("torque", [195] * 6) in s.driver.writes
