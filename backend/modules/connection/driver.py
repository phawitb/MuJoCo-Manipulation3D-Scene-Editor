"""Feetech STS3215 protocol 0. No EEPROM/calibration/torque-off writes."""

import hashlib
import json
import os
import subprocess
import tempfile
import time


def canonical_port(path):
    return os.path.realpath(path).replace("/dev/tty.", "/dev/cu.")


def discover_ports():
    try:
        from serial.tools import list_ports
    except ImportError:
        return {"ports": [], "error": "Install pyserial to discover serial ports"}
    return {
        "ports": [
            dict(
                port=p.device,
                description=p.description,
                serial_number=p.serial_number,
                vid=p.vid,
                pid=p.pid,
            )
            for p in list_ports.comports()
        ]
    }


class SerialDriver:
    def __init__(self, port):
        self.path = port
        self.port = None
        self.guard = None
        self.models = []
        self.identity = None
        self.temperature_rechecks = 0
        self.last_temperature_check = None

    def open(self):
        try:
            import fcntl
            from scservo_sdk import PortHandler, PacketHandler
            from serial.tools import list_ports
        except ImportError as exc:
            raise RuntimeError(
                "Install pyserial and feetech-servo-sdk to connect the arm"
            ) from exc
        try:
            # Check existing users before SDK opens/resets its input buffer.
            canonical = canonical_port(self.path)
            aliases = {self.path, canonical, canonical.replace("/dev/cu.", "/dev/tty.")}
            busy = subprocess.run(
                ["lsof", "-t", *sorted(aliases)],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if busy.stdout.strip():
                raise RuntimeError("Serial port is already open in another process")
            lockpath = os.path.join(
                tempfile.gettempdir(),
                "so101-" + hashlib.sha256(canonical.encode()).hexdigest() + ".lock",
            )
            self.guard = open(lockpath, "a")
            fcntl.flock(self.guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.port = PortHandler(self.path)
            self.packet = PacketHandler(0)
            if not self.port.setBaudRate(1_000_000):
                raise RuntimeError("Cannot set serial baud rate to 1 Mbps")
            self.port.ser.exclusive = True
            for motor in range(1, 7):
                model, result, error = self.packet.ping(self.port, motor)
                try:
                    self._check(result, error)
                except IOError as exc:
                    raise IOError(
                        f"Motor {motor} did not verify at 1 Mbps. Check motor power, cable and IDs 1–6: {exc}"
                    ) from exc
                if model != 777:
                    raise RuntimeError(
                        f"Motor {motor} is model {model}; expected STS3215 model 777"
                    )
                self.models.append(model)
            entry = next(
                (p for p in list_ports.comports() if p.device == self.path), None
            )
            self.identity = json.dumps(
                dict(
                    port=self.path,
                    serial=getattr(entry, "serial_number", None),
                    vid=getattr(entry, "vid", None),
                    pid=getattr(entry, "pid", None),
                    models=self.models,
                ),
                sort_keys=True,
            )
        except Exception:
            self.close()
            raise

    def _check(self, result, error):
        if result != 0 or error:
            raise IOError(
                f"Feetech communication failure: {self.packet.getTxRxResult(result)}; device error {error}"
            )

    def _read(self, motor, address, size=1):
        value, result, error = getattr(self.packet, f"read{size}ByteTxRx")(
            self.port, motor, address
        )
        self._check(result, error)
        return value

    def _feedback_frame(self, motor):
        # SDK txRxPacket checks checksum/device errors. Inspect the raw length:
        # readTxRx slices the response and may include a short packet's checksum.
        request = [0, 0, motor, 4, 2, 40, 30, 0]  # READ RAM 40..69
        packet, result, error = self.packet.txRxPacket(self.port, request)
        self._check(result, error)
        if len(packet) != 36 or packet[3] != 32 or packet[2] != motor:
            raise IOError(f"Incomplete feedback frame from motor {motor}")
        frame = packet[5:-1]
        if not 40 <= frame[22] <= 140:
            raise IOError(
                f"Unsafe voltage feedback from motor {motor}: {frame[22] / 10}"
            )
        return frame

    def read(self):
        rows = []
        for motor in range(1, 7):
            frame = self._feedback_frame(motor)
            if frame[23] >= 50:
                # Physical probes observed isolated 36→78→36 C spikes. No goal
                # writes occur during confirmation. Require three agreeing
                # samples out of at most five; two hot samples always fault.
                readings = [frame[23]]
                self.temperature_rechecks += 1
                self.last_temperature_check = {"motor": motor, "readings": readings}
                confirmed = None
                for _ in range(4):
                    time.sleep(0.002)
                    frame = self._feedback_frame(motor)
                    readings.append(frame[23])
                    if sum(value >= 65 for value in readings) >= 2:
                        break
                    ordered = sorted(value for value in readings if value < 65)
                    clusters = [
                        ordered[i : i + 3]
                        for i in range(len(ordered) - 2)
                        if ordered[i + 2] - ordered[i] <= 3
                    ]
                    if clusters:
                        confirmed = max(max(cluster) for cluster in clusters)
                        break
                if confirmed is None:
                    raise IOError(
                        f"Unsafe or inconsistent temperature on motor {motor}: {readings}"
                    )
                frame[23] = confirmed
            raw = frame[16] | frame[17] << 8
            if raw & 0x8000:
                raw = -(raw & 0x7FFF)
            rows.append(
                dict(
                    id=motor,
                    model=self.models[motor - 1],
                    raw=raw,
                    goal_raw=frame[2] | frame[3] << 8,
                    goal_velocity_raw=frame[6] | frame[7] << 8,
                    present_speed_raw=frame[18] | frame[19] << 8,
                    present_load_raw=frame[20] | frame[21] << 8,
                    torque_limit_raw=frame[8] | frame[9] << 8,
                    servo_status_raw=frame[25],
                    moving=bool(frame[26]),
                    voltage=frame[22] / 10.0,
                    temperature=frame[23],
                    torque=bool(frame[0]),
                )
            )
        return rows

    def goals(self, values):
        for motor, value in enumerate(values, 1):
            if not 0 <= value <= 4095:
                raise ValueError("Goal outside single-turn encoder range")
            self._check(*self.packet.write2ByteTxRx(self.port, motor, 42, int(value)))

    def torque(self, speeds=None):
        # STS3215 Goal_Velocity (RAM 46, uint16): ticks/s. 195 = 0.299 rad/s.
        for motor, speed in enumerate(speeds or [195] * 6, 1):
            self._check(*self.packet.write2ByteTxRx(self.port, motor, 46, speed))
        for motor in range(1, 7):
            self._check(*self.packet.write1ByteTxRx(self.port, motor, 40, 1))

    def close(self):
        if self.port:
            self.port.closePort()
            self.port = None
        if self.guard:
            self.guard.close()
            self.guard = None
