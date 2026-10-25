"""Real MuJoCo/IK/collision integration with ideal encoder feedback, not hardware.

The fake bus jumps to each quantized solved endpoint. These tests exercise
whole-arm swept guards and object-world transitions, not servo dynamics or
independent physical grasp verification.
"""

import threading
from types import SimpleNamespace

import numpy as np
import pytest

from backend.examples import example_scene
from backend.planning import calculate_plan
from backend.simulation import Simulation
from backend.modules.connection.bridge import GymBridge
from backend.modules.connection.service import ConnectionService
from backend.tests.test_connection import calibrated
from backend.tests.test_manual_controls import Bus


@pytest.mark.parametrize(
    "example", ["kalas-cup-front", "kalas-cup-left", "kalas-cup-right"]
)
def test_rehearsed_tool_goals_with_quantized_feedback(example, tmp_path):
    sim = Simulation(example_scene(example))
    plan = calculate_plan(sim)
    assert plan["verified"], plan["message"]
    before = sim.data.qpos.copy()
    session = SimpleNamespace(
        sim=sim,
        id="one",
        lock=threading.RLock(),
        closed=False,
        packet=lambda: {},
        broadcast=lambda _: None,
    )
    registry = SimpleNamespace(get=lambda _: session)
    service = ConnectionService(
        settings_dir=tmp_path,
        driver_factory=Bus,
        bridge_factory=lambda _, sid: GymBridge(registry, sid),
        start_worker=False,
    )
    try:
        calibrated(service)
        service.driver.raw = service._raw(sim.data.qpos[:6])
        waypoints = plan["cartesian_waypoints"]
        service.execution.start(session, sim, waypoints)
        for _ in range(len(waypoints) + 10):
            if not service.execution.active:
                break
            service.driver.raw = service._raw(service.manual.target)
            service.heartbeat("one")
            service.tick()
        assert service.execution.phase == "completed", service.fault
        assert service.execution.index == len(waypoints)
        assert service.fault is None
        assert np.array_equal(sim.data.qpos, before)
        report = service.execution.report
        assert report["last_error"]["position_mm"] < 3
        assert report["measurement_source"] == "encoder_fk"
        assert report["object_verified"] is False
    finally:
        service.shutdown()
