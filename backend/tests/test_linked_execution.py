import threading
from types import SimpleNamespace
import numpy as np
import pytest
from backend.sessions import Command, Session
from backend.modules.connection.service import ConnectionService, ConnectionError
from backend.tests.test_connection import Driver, Bridge, calibrated


class SceneSession:
    def __init__(self):
        self.id = "one"
        self.lock = threading.RLock()
        self.closed = False
        self.external_clock = False
        self.sim = SimpleNamespace(
            running=False,
            data=SimpleNamespace(qpos=np.zeros(6)),
            policy=SimpleNamespace(status="idle", message=""),
        )
        self.ready = True
        self.steps = 0
        self.packets = []

    def validate_run(self):
        if not self.ready:
            raise ValueError("Calculate a successful path")

    def execute(self, command):
        self.sim.running = command.type == "run"
        if command.type == "run":
            self.sim.policy.status = "running"
        return {"type": "snapshot"}

    def packet(self):
        return {"type": "snapshot"}

    def tick(self, count, **kwargs):
        self.steps += count
        self.sim.data.qpos[0] += 0.002 * count
        return {"type": "state"}

    def broadcast(self, packet):
        self.packets.append(packet)


@pytest.fixture
def linked(tmp_path):
    service = ConnectionService(
        settings_dir=tmp_path,
        driver_factory=Driver,
        bridge_factory=Bridge,
        start_worker=False,
    )
    calibrated(service)
    yield service, SceneSession()
    service.shutdown()


def test_run_connected_enables_sync_and_external_clock(linked):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    assert service.enabled and service.sync_mode == "gym_to_real"
    assert session.external_clock and session.sim.running
    assert service.status()["gym_execution"]["phase"] == "running"


def test_invalid_plan_never_enables_hardware(linked):
    service, session = linked
    session.ready = False
    with pytest.raises(ValueError, match="Calculate"):
        service.scene_command(session, Command(type="run"))
    assert service.driver.writes == []
    assert not session.external_clock and not service.enabled


def test_linked_clock_waits_for_measured_angles_and_advances_in_small_steps(linked):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    session.sim.data.qpos[0] = 0.1
    service.execution.advance([0] * 6)
    assert session.steps == 0
    session.sim.data.qpos[0] = 0
    service.execution.advance([0] * 6)
    assert 1 <= session.steps <= 4
    assert session.sim.data.qpos[0] <= 0.008
    assert session.packets


def test_fault_and_global_stop_pause_simulation_too(linked):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    service.stop("one")
    assert not session.sim.running and not session.external_clock
    assert not service.enabled and service.sync_mode == "off"
    service.scene_command(session, Command(type="run"))
    service.driver.broken = True
    service.tick()
    assert not session.sim.running and not session.external_clock
    assert not service.enabled


def test_other_session_run_cannot_claim_connected_robot(linked):
    service, session = linked
    session.id = "other"
    with pytest.raises(ConnectionError, match="another Gym"):
        service.scene_command(session, Command(type="run"))
    assert not session.sim.running and service.driver.writes == []


def test_session_wall_clock_does_not_advance_external_clock():
    session = Session()
    session.external_clock = True
    session.sim.running = True
    before = session.sim.data.time
    assert session.tick(30) is None
    assert session.sim.data.time == before


def test_start_pose_difference_rejected_before_any_motor_write(linked):
    service, session = linked
    session.sim.data.qpos[2] = 0.1
    with pytest.raises(ValueError, match="moved since"):
        service.scene_command(session, Command(type="run"))
    assert service.driver.writes == []


def test_final_pose_settles_before_linked_run_completes(linked):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    session.sim.running = False
    session.sim.policy.status = "succeeded"
    for _ in range(4):
        service.execution.advance([0] * 6)
    assert service.execution.active and service.enabled
    service.execution.advance([0] * 6)
    assert service.execution.phase == "completed"
    assert not service.enabled and service.sync_mode == "off"
    assert not session.external_clock


def test_stalled_robot_pauses_instead_of_advancing_simulation(linked):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    session.sim.data.qpos[0] = 0.1
    service.execution.last_progress = 0
    with pytest.raises(ValueError, match="cannot follow"):
        service.execution.advance([0] * 6)
    assert session.steps == 0


def test_connected_pause_stops_both_clocks(linked):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    service.scene_command(session, Command(type="pause"))
    assert not session.sim.running and not session.external_clock
    assert not service.enabled


@pytest.mark.parametrize("during_step", [False, True])
def test_failed_policy_stops_hardware_before_passive_open_gripper_settling(
    linked, during_step
):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    if during_step:

        def fail_tick(count, **kwargs):
            session.steps += count
            session.sim.policy.status = "failed"
            session.sim.policy.message = "Grasp lost"
            session.sim.data.qpos[5] = 0.02
            return {"type": "state"}

        session.tick = fail_tick
    else:
        session.sim.policy.status = "failed"
        session.sim.policy.message = "Grasp lost"
    before = len(service.driver.writes)
    service.tick()
    assert not service.enabled and not service.execution.active
    assert not session.sim.running and not session.external_clock
    assert "Grasp lost" in service.fault
    assert session.steps == (1 if during_step else 0)
    assert all(
        values == [2048] * 6
        for kind, values in service.driver.writes[before:]
        if kind == "goals"
    )


def test_physics_command_stops_linked_hardware_before_switching_mode(linked):
    from backend.modules.gym.routes import execute

    service, session = linked
    service.scene_command(session, Command(type="run"))
    app = SimpleNamespace(state=SimpleNamespace(connection=service))
    execute(app, session, Command(type="physics"))
    assert not service.enabled and not service.execution.active
    assert not session.external_clock


def test_scene_replacement_clears_previous_execution_status(linked):
    service, session = linked
    service.scene_command(session, Command(type="run"))
    service.stop("one")
    assert service.execution.phase == "paused"
    service.replace_scene(session, Command(type="example"))
    assert service.execution.phase == "idle"
    assert not service.enabled
