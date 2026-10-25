import math
import time
import pytest
from backend.modules.connection.service import (
    ConnectionService,
    ConnectionError,
    JOINT_NAMES,
)
from backend.modules.connection.schemas import Calibration


class Driver:
    def __init__(self, port):
        self.port = port
        self.identity = "usb:fake:777,777,777,777,777,777"
        self.raw = [2048] * 6
        self.writes = []
        self.broken = False

    def open(self):
        pass

    def close(self):
        pass

    def read(self):
        if self.broken:
            raise IOError("unplugged")
        return [
            dict(id=i + 1, model=777, raw=q, voltage=7.4, temperature=25, torque=False)
            for i, q in enumerate(self.raw)
        ]

    def goals(self, values):
        self.writes.append(("goals", list(values)))
        self.raw = list(values)

    def torque(self, speeds=None):
        self.writes.append(("torque", True))


class Bridge:
    def __init__(self, registry, session_id):
        self.q = [0.0] * 6
        self.collision = False
        self.closed = False

    def check_alive(self):
        if self.closed:
            raise ConnectionError("Session closed")

    def get(self):
        self.check_alive()
        return list(self.q)

    def validate(self, start, end):
        self.check_alive()
        if self.collision:
            raise ConnectionError("Simulation collision")
        if max(abs(q) for q in end) > 2:
            raise ConnectionError("Simulation joint limit")

    def set(self, q):
        self.q = list(q)


@pytest.fixture
def service(tmp_path):
    s = ConnectionService(
        settings_dir=tmp_path,
        driver_factory=Driver,
        bridge_factory=Bridge,
        start_worker=False,
    )
    yield s
    s.shutdown()


def calibrated(s):
    s.connect("/dev/fake", "one", None)
    s.save_calibration(
        Calibration(
            session_id="one",
            identity=s.identity,
            confirmed=True,
            joints=[
                dict(name=n, zero_raw=2048, direction=1, raw_min=100, raw_max=4000)
                for n in JOINT_NAMES
            ],
        )
    )
    return s


def test_connect_is_readonly_and_uncalibrated_enable_never_writes(service):
    status = service.connect("/dev/fake", "one", None)
    assert status["connected"] and not status["calibrated"]
    assert all(j["position_rad"] is None for j in status["telemetry"])
    with pytest.raises(ConnectionError, match="calibration"):
        service.enable("one")
    assert service.driver.writes == []


def test_enable_seeds_measured_hold_before_torque_and_jog_bounded(service):
    s = calibrated(service)
    s.enable("one")
    assert s.driver.writes[:2] == [("goals", [2048] * 6), ("torque", True)]
    s.jog("one", 0, 0.03)
    assert s.driver.raw[0] == 2048 + round(0.03 / (2 * math.pi / 4096))
    with pytest.raises(ConnectionError):
        s.jog("one", 0, 0.2)


def test_wrong_owner_collision_and_limit_prohibit_writes(service):
    s = calibrated(service)
    s.enable("one")
    before = len(s.driver.writes)
    with pytest.raises(ConnectionError):
        s.jog("two", 0, 0.01)
    s.bridge.collision = True
    with pytest.raises(ConnectionError, match="collision"):
        s.jog("one", 0, 0.01)
    assert len(s.driver.writes) == before


def test_identity_mismatch_and_reconnect_require_explicit_enable(service):
    s = calibrated(service)
    s.enable("one")
    s.disconnect("one")
    assert not s.connect("/dev/fake", "one", None)["enabled"]
    assert s.status()["calibrated"]
    s.calibration.identity = "other"
    with pytest.raises(ConnectionError):
        s.enable("one")
    assert s.driver.writes == []


def test_lease_expiry_holds_and_stops_stream(service):
    s = calibrated(service)
    s.enable("one")
    s.sync("one", "gym_to_real")
    s.lease_until = time.monotonic() - 1
    s.tick()
    assert not s.enabled and s.sync_mode == "off" and "heartbeat" in s.fault
    assert not any(w == ("torque", False) for w in s.driver.writes)


def test_serial_failure_stops_new_commands_without_torque_release(service):
    s = calibrated(service)
    s.enable("one")
    before = len(s.driver.writes)
    s.driver.broken = True
    s.tick()
    assert not s.enabled and "unplugged" in s.fault
    assert len(s.driver.writes) == before


def test_tracking_jump_stops_sync(service):
    s = calibrated(service)
    s.enable("one")
    s.sync("one", "gym_to_real")
    s.driver.raw[0] += 500
    s.tick()
    assert not s.enabled and "tracking" in s.fault.lower()


def test_real_to_gym_never_writes_and_updates_measured_pose(service):
    s = calibrated(service)
    s.sync("one", "real_to_gym")
    s.driver.raw[0] += 10
    s.tick()
    assert s.bridge.q[0] == pytest.approx(10 * math.tau / 4096)
    assert s.driver.writes == []


def test_settings_persist_but_motion_does_not(service, tmp_path):
    calibrated(service)
    service.assign_cameras(dict(back=0, front=1, wrist=None))
    s = ConnectionService(settings_dir=tmp_path, start_worker=False)
    assert s.settings()["assignments"] == dict(back=0, front=1, wrist=None)
    assert s.settings()["calibration"]["confirmed"]
    assert not s.connected and not s.enabled
    s.shutdown()


def test_rapid_repeated_jogs_cannot_bypass_velocity_guard(service):
    s = calibrated(service)
    s.enable("one")
    delta = 20 * math.tau / 4096
    s.jog("one", 0, delta)
    with pytest.raises(ConnectionError, match="velocity"):
        s.jog("one", 0, delta)


def test_raw_bounds_block_every_physical_write(service):
    s = calibrated(service)
    s.calibration.joints[0].raw_max = 2049
    s.enable("one")
    before = len(s.driver.writes)
    with pytest.raises(ConnectionError, match="limit"):
        s.jog("one", 0, 0.03)
    assert len(s.driver.writes) == before


def test_large_initial_difference_blocks_sync(service):
    s = calibrated(service)
    s.enable("one")
    s.bridge.q[0] = 0.2
    with pytest.raises(ConnectionError, match="Initial"):
        s.sync("one", "gym_to_real")
    assert s.sync_mode == "off"


def test_deleted_session_stops_stream_but_owner_can_disconnect(service):
    s = calibrated(service)
    s.enable("one")
    s.bridge.closed = True
    s.tick()
    assert not s.enabled
    assert not s.disconnect("one")["connected"]


def test_camera_deadline_and_exclusive_assignments(service):
    import subprocess
    from backend.modules.connection.cameras import CameraService

    def stalled(*args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    cameras = CameraService(runner=stalled)
    assert "timed out" in cameras.scan(0)[0]["error"]
    with pytest.raises(ValueError, match="one role"):
        service.assign_cameras(dict(back=0, front=0, wrist=None))


def test_typed_router_validates_and_uses_shared_service(service):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.modules.connection.routes import create_router

    app = FastAPI()
    app.state.sessions = None
    app.include_router(create_router(service))
    with TestClient(app) as c:
        assert c.get("/api/connection/status").json()["connected"] is False
        assert (
            c.post(
                "/api/connection/connect", json=dict(port="/tmp/file", session_id="one")
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/connection/connect",
                json=dict(port="/dev/ttyFAKE", session_id="one"),
            ).status_code
            == 200
        )
        assert (
            c.post(
                "/api/connection/jog",
                json=dict(session_id="one", joint=0, delta_rad=0.1),
            ).status_code
            == 422
        )
        assert (
            c.post("/api/connection/enable", json=dict(session_id="one")).status_code
            == 409
        )
        assert (
            c.post("/api/connection/align", json={"session_id": "one"}).status_code
            == 409
        )
        assert c.get("/api/connection/cameras/10/frame").status_code == 422


def test_driver_limits_speed_before_any_torque_enable():
    from backend.modules.connection.driver import SerialDriver

    class Packet:
        def __init__(self):
            self.writes = []

        def write1ByteTxRx(self, port, motor, address, value):
            self.writes.append((motor, address, value))
            return 0, 0

        def write2ByteTxRx(self, port, motor, address, value):
            self.writes.append((motor, address, value))
            return 0, 0

    driver = SerialDriver("/dev/fake")
    driver.packet = Packet()
    driver.port = object()
    driver.torque()
    for motor in range(1, 7):
        assert driver.packet.writes.index(
            (motor, 46, 195)
        ) < driver.packet.writes.index((motor, 40, 1))


def test_stale_serial_read_disables_motion(service, monkeypatch):
    s = calibrated(service)
    s.enable("one")
    original = s.driver.read

    def slow():
        rows = original()
        clock[0] += 2
        return rows

    clock = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    s.driver.read = slow
    s.tick()
    assert not s.enabled and "Stale" in s.fault


def test_warm_motor_blocks_read_only_handshake(service):
    original = Driver.read

    def hot(self):
        rows = original(self)
        rows[0]["temperature"] = 70
        return rows

    service.driver_factory = lambda port: type("Hot", (Driver,), {"read": hot})(port)
    with pytest.raises(ConnectionError, match="temperature"):
        service.connect("/dev/fake", "one", None)
    assert not service.connected


def test_speed_bound_accounts_for_nonstandard_calibration_scale(service):
    s = calibrated(service)
    s.calibration.joints[5].radians_per_tick = 0.01
    captured = []
    s.driver.torque = lambda speeds: captured.extend(speeds)
    s.enable("one")
    assert captured == [195] * 5 + [30]


def test_macos_serial_aliases_share_lock_identity():
    from backend.modules.connection.driver import canonical_port

    assert canonical_port("/dev/tty.usbmodem123") == canonical_port(
        "/dev/cu.usbmodem123"
    )


def test_real_gym_bridge_mirrors_measured_pose_and_guards_changes():
    from backend.sessions import Session
    from backend.modules.connection.bridge import GymBridge

    class Registry:
        def __init__(self, session):
            self.s = session

        def get(self, sid):
            return self.s

    session = Session()
    bridge = GymBridge(Registry(session), "one")
    current = bridge.get()
    bridge.validate(current, current)
    bridge.set(current)
    assert session.packet()["joints"] == current
    assert session.plan_dirty and not session.sim.running
    invalid = list(current)
    invalid[0] = 10
    with pytest.raises(ValueError, match="limit"):
        bridge.validate(current, invalid)
    session.closed = True
    with pytest.raises(ValueError, match="closed"):
        bridge.get()


def test_new_simulation_collision_stops_stream_with_measured_hold(service):
    s = calibrated(service)
    s.enable("one")
    s.sync("one", "gym_to_real")
    s.bridge.collision = True
    before = len(s.driver.writes)
    s.tick()
    assert not s.enabled and s.sync_mode == "off"
    assert "collision" in s.fault
    assert s.driver.writes[before:] == [("goals", [2048] * 6)]


def test_measured_pose_mirroring_cancels_active_gym_policy():
    from backend.sessions import Session
    from backend.modules.connection.bridge import GymBridge

    session = Session()
    registry = type("Registry", (), {"get": lambda self, sid: session})()
    bridge = GymBridge(registry, "one")
    session.sim.policy.status = "running"
    session.sim.running = True
    bridge.set(bridge.get())
    assert session.sim.policy.status == "cancelled"


def test_gym_collision_guard_rechecks_reloaded_scene():
    from backend.sessions import Session
    from backend.schema import SceneObject
    from backend.modules.connection.bridge import GymBridge

    session = Session()
    registry = type("Registry", (), {"get": lambda self, sid: session})()
    bridge = GymBridge(registry, "one")
    current = bridge.get()
    scene = session.sim.export_scene()
    scene.objects.append(
        SceneObject(
            id="obstacle",
            name="Obstacle",
            asset="cube",
            scale=3,
            position=session.sim.data.body("gripper").xpos.tolist(),
        )
    )
    session.sim.load(scene)
    with pytest.raises(ValueError, match="collision"):
        bridge.validate(current, current)


def test_half_tick_calibration_zero_preserves_physical_midpoint(service):
    s = calibrated(service)
    value = s.calibration.model_dump()
    value["joints"][0]["zero_raw"] = 2111.5
    s.save_calibration(Calibration.model_validate(value))
    assert s._angle(0, 2111) == pytest.approx(-math.pi / 4096)
    assert s._angle(0, 2112) == pytest.approx(math.pi / 4096)
    assert s._raw([s._angle(i, 2048) for i in range(6)]) == [2048] * 6


def test_sync_command_ramp_crosses_servo_deadband(service, monkeypatch):
    s = calibrated(service)
    clock = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    s.enable("one")
    s.sync("one", "gym_to_real")
    s.bridge.q[0] = 0.1

    def deadband_goals(values):
        s.driver.writes.append(("goals", list(values)))
        for i, value in enumerate(values):
            if abs(value - s.driver.raw[i]) >= 15:
                s.driver.raw[i] = value

    s.driver.goals = deadband_goals
    for _ in range(30):
        clock[0] += 0.02
        s.tick()
    assert s.enabled and s.sync_mode == "gym_to_real"
    assert s.driver.raw[0] > 2080
    assert s.target_rad[0] == pytest.approx(0.1)


def test_command_ramp_still_stops_a_stalled_motor(service, monkeypatch):
    s = calibrated(service)
    clock = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    s.enable("one")
    s.sync("one", "gym_to_real")
    s.bridge.q[0] = 0.2
    s.driver.goals = lambda values: s.driver.writes.append(("goals", list(values)))
    for _ in range(40):
        clock[0] += 0.02
        s.tick()
    assert not s.enabled and s.sync_mode == "off"
    assert "tracking" in s.fault.lower()


def test_command_ramp_never_sends_excessive_lead_over_feedback(service, monkeypatch):
    s = calibrated(service)
    clock = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    s.enable("one")
    s.sync("one", "gym_to_real")
    s.bridge.q[0] = 0.25
    s.target_rad[0] = 0.14
    before = len(s.driver.writes)
    clock[0] += 0.1
    s.tick()
    assert not s.enabled and "tracking" in s.fault.lower()
    assert s.driver.writes[before:] == [("goals", [2048] * 6)]


def test_align_gym_uses_measured_pose_without_motor_commands(service):
    s = calibrated(service)
    s.driver.raw[0] += 30
    s.align("one")
    assert s.bridge.q[0] == pytest.approx(30 * math.tau / 4096)
    assert s.driver.writes == [] and not s.enabled and s.sync_mode == "off"
    with pytest.raises(ConnectionError, match="owned"):
        s.align("another")
    s.enable("one")
    with pytest.raises(ConnectionError, match="Stop"):
        s.align("one")


def test_align_rejects_collision_and_active_read_only_sync(service):
    s = calibrated(service)
    original = list(s.bridge.q)
    s.driver.raw[0] += 30
    s.bridge.collision = True
    with pytest.raises(ConnectionError, match="collision"):
        s.align("one")
    assert s.bridge.q == original and s.driver.writes == []
    s.bridge.collision = False
    s.sync("one", "real_to_gym")
    with pytest.raises(ConnectionError, match="Stop"):
        s.align("one")
    assert s.driver.writes == []
