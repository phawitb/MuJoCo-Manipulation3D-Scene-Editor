"""Decode checked STS3215 frames and confirm implausible thermal readings."""

import pytest
from backend.modules.connection.driver import SerialDriver


class Packet:
    def __init__(self, *, length=30, result=0, error=0, temperatures=None):
        self.calls = []
        self.length, self.result, self.error = length, result, error
        self.temperatures = iter(temperatures or [])

    def txRxPacket(self, port, request):
        motor, address, length = request[2], request[5], request[6]
        self.calls.append((motor, address, length))
        payload = [0] * max(30, self.length)
        raw = 2048 + motor if motor != 6 else 0x8005
        payload[0] = 1
        payload[2:4] = [100, 8]
        payload[6:10] = [195, 0, 232, 3]
        payload[18:22] = [4, 0, 84, 0]
        payload[25:27] = [0, 1]
        payload[16:18] = [raw & 255, raw >> 8]
        payload[22:24] = [122, next(self.temperatures, 35 + motor)]
        packet = [255, 255, motor, self.length + 2, self.error] + payload[: self.length]
        packet.append((~sum(packet[2:])) & 255)
        return packet, self.result, self.error

    def readTxRx(self, port, motor, address, length):
        # Exactly the installed SDK's slicing, including checksum on short packets.
        packet, result, error = self.txRxPacket(
            port, [0, 0, motor, 4, 2, address, length, 0]
        )
        return packet[5 : 5 + length], result, error

    def getTxRxResult(self, result):
        return str(result)


def driver(packet):
    d = SerialDriver("/not-opened")
    d.models = [777] * 6
    d.packet = packet
    return d


def test_feedback_is_one_coherent_frame_per_motor():
    packet = Packet()
    rows = driver(packet).read()
    assert packet.calls == [(i, 40, 30) for i in range(1, 7)]
    assert [r["raw"] for r in rows] == [2049, 2050, 2051, 2052, 2053, -5]
    assert [r["temperature"] for r in rows] == [36, 37, 38, 39, 40, 41]
    assert all(r["voltage"] == 12.2 and r["torque"] for r in rows)
    assert all(r["goal_raw"] == 2148 and r["goal_velocity_raw"] == 195 for r in rows)
    assert all(
        r["torque_limit_raw"] == 1000 and r["servo_status_raw"] == 0 for r in rows
    )
    assert all(
        r["present_speed_raw"] == 4 and r["present_load_raw"] == 84 and r["moving"]
        for r in rows
    )


@pytest.mark.parametrize("length", [0, 1, 2, 8, 29, 31])
def test_wrong_payload_length_never_passes_as_complete_feedback(length):
    with pytest.raises(IOError, match="Incomplete"):
        driver(Packet(length=length)).read()


@pytest.mark.parametrize("result,error", [(-1, 0), (0, 4)])
def test_transport_and_motor_error_reject_entire_feedback(result, error):
    with pytest.raises(IOError, match="communication"):
        driver(Packet(result=result, error=error)).read()


def test_single_thermal_spike_requires_two_agreeing_fresh_readings():
    d = driver(Packet(temperatures=[78, 36, 37, 36]))
    rows = d.read()
    assert rows[0]["temperature"] == 37
    assert d.temperature_rechecks == 1
    assert d.last_temperature_check == {"motor": 1, "readings": [78, 36, 37, 36]}
    assert d.packet.calls[:4] == [(1, 40, 30)] * 4


def test_confirmed_overtemperature_remains_unsafe():
    d = driver(Packet(temperatures=[78, 77, 78]))
    with pytest.raises(IOError, match="temperature"):
        d.read()


def test_disagreeing_rechecks_are_not_silently_averaged():
    with pytest.raises(IOError, match="temperature"):
        driver(Packet(temperatures=[78, 36, 56, 45, 60])).read()


def test_two_thermal_outliers_need_three_agreeing_low_samples():
    d = driver(Packet(temperatures=[77, 36, 48, 36, 36]))
    assert d.read()[0]["temperature"] == 36
    assert d.last_temperature_check["readings"] == [77, 36, 48, 36, 36]


def test_two_hot_samples_always_fault_even_with_cold_samples_between():
    with pytest.raises(IOError, match="temperature"):
        driver(Packet(temperatures=[78, 36, 77, 36, 36])).read()


class RegisterPacket:
    def __init__(self):
        self.speed = [0, 500, 600, 0, 700, 0]
        self.writes = []

    def read2ByteTxRx(self, port, motor, address):
        return self.speed[motor - 1], 0, 0

    def write2ByteTxRx(self, port, motor, address, value):
        self.writes.append((motor, address, value))
        if address == 46:
            self.speed[motor - 1] = value
        return 0, 0

    def write1ByteTxRx(self, port, motor, address, value):
        self.writes.append((motor, address, value))
        return 0, 0


def test_speed_override_restores_original_after_staging_measured_hold():
    packet = RegisterPacket()
    d = driver(packet)
    d.read = lambda: [dict(raw=2000 + i) for i in range(6)]
    d.torque([195] * 6)
    assert packet.speed == [195] * 6
    d.restore_speed()
    assert packet.speed == [0, 500, 600, 0, 700, 0]
    assert packet.writes[-12:-6] == [(i + 1, 42, 2000 + i) for i in range(6)]
    assert not d.speed_overridden


def test_explicit_legacy_repair_restores_zero_without_torque_writes():
    packet = RegisterPacket()
    packet.speed = [195] * 6
    d = driver(packet)
    d.read = lambda: [dict(raw=2000 + i) for i in range(6)]
    d.restore_speed(default=True)
    assert packet.speed == [0] * 6
    assert all(address != 40 for _, address, _ in packet.writes)


def test_close_releases_port_even_when_profile_restoration_fails():
    from unittest.mock import Mock

    d = driver(RegisterPacket())
    port, guard = Mock(), Mock()
    d.port, d.guard = port, guard
    d.torque()
    d.read = Mock(side_effect=IOError("lost feedback"))
    with pytest.raises(IOError, match="lost feedback"):
        d.close()
    port.closePort.assert_called_once()
    guard.close.assert_called_once()
    assert d.port is None and d.guard is None
