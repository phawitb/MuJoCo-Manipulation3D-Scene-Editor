import threading
from types import SimpleNamespace
import numpy as np
import pytest
from backend.modules.connection.service import ConnectionService
from backend.tests.test_connection import Driver, Bridge, calibrated


class SceneSession:
    def __init__(self):
        self.id = "one"
        self.lock = threading.RLock()
        self.closed = False
        self.sim = SimpleNamespace(
            running=False,
            data=SimpleNamespace(qpos=np.zeros(6)),
            policy=SimpleNamespace(status="idle", message=""),
        )
        self.packets = []

    def execute(self, command):
        self.sim.running = command.type == "run"
        if command.type == "run":
            self.sim.policy.status = "running"
        return {"type": "snapshot"}

    def packet(self):
        return {"type": "snapshot"}

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
