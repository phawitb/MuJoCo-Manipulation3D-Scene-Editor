import pytest
from backend.simulation import Simulation
from backend.modules.connection.retreat import TableRetreatGuard

Q = [0.307563, 0.473233, -0.074398, 1.205709, -1.20801, 0.03835]


def test_only_separating_table_retreat_is_accepted():
    sim = Simulation()
    guard = TableRetreatGuard(sim, Q)
    raised = list(Q)
    raised[1] -= 0.10
    guard.path(Q, raised)
    lower = list(Q)
    lower[1] += 0.02
    with pytest.raises(ValueError, match="deepen"):
        guard.path(Q, lower)


def test_retreat_rejects_safe_pose_or_deep_collision():
    sim = Simulation()
    with pytest.raises(ValueError):
        TableRetreatGuard(sim, sim.data.qpos[:6])
    deep = list(Q)
    deep[1] += 0.05
    with pytest.raises(ValueError, match="at most 8"):
        TableRetreatGuard(sim, deep)


def test_retreat_can_clear_table_without_increasing_stalled_shoulder_goal():
    from backend.modules.connection.retreat import choose_retreat
    sim = Simulation()
    held = list(Q)
    held[1] -= 0.08
    target = choose_retreat(TableRetreatGuard(sim, Q), Q, held)
    assert target[1] == held[1]
    assert target[2] < held[2]
    TableRetreatGuard(sim, Q).path(Q, target)


@pytest.mark.parametrize('outcome', ['success', 'tracking', 'lease', 'scene'])
def test_retreat_loop_stops_on_fault_and_preserves_last_goal(tmp_path, monkeypatch, outcome):
    from backend.modules.connection.service import ConnectionService
    from backend.tests.test_connection import Driver, Bridge, calibrated
    from backend.sessions import Session
    from backend.modules.connection import retreat as module

    class HeldDriver(Driver):
        def read(self):
            rows = super().read()
            for row, goal in zip(rows, self.held):
                row.update(torque=True, goal_raw=goal)
            return rows

        def goals(self, values):
            self.writes.append(('goals', list(values)))
            self.held = list(values)
            if outcome != 'tracking':
                self.raw = list(values)

        def open(self):
            self.held = list(self.raw)

    service = ConnectionService(settings_dir=tmp_path, driver_factory=HeldDriver,
                                bridge_factory=Bridge, start_worker=False)
    calibrated(service)
    scene = Session()
    service.bridge.session = lambda: scene
    service.driver.raw = service._raw(Q)
    service.driver.held = list(service.driver.raw)
    clock = [100.0]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])

    def advance(seconds):
        clock[0] += seconds
        if outcome != 'lease':
            service.heartbeat('one')
        if outcome == 'scene':
            scene.sim = Simulation()

    monkeypatch.setattr(module.time, 'sleep', advance)
    try:
        if outcome == 'success':
            result = service.retreat('one')
            assert result['fault'] is None
            assert service.tracker is not None
        else:
            message = {'tracking': 'tracking', 'lease': 'heartbeat', 'scene': 'Scene changed'}[outcome]
            with pytest.raises(ValueError, match=message):
                service.retreat('one')
        assert not service.enabled and not service.recovering
        assert service.sync_mode == 'off'
        assert service.driver.writes
        assert all(kind == 'goals' for kind, _ in service.driver.writes)
        assert service.driver.held == service.driver.writes[-1][1]
    finally:
        service.shutdown()
