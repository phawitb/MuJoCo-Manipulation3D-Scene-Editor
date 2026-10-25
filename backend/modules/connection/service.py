"""One serialized hardware owner, conservative physical motion, local settings."""

import json
import math
import secrets
import os
from pathlib import Path
import tempfile
import threading
import time
from .schemas import Calibration, Assignments, RobotPort, JOINT_NAMES
from .driver import SerialDriver
from .bridge import GymBridge
from .tracking import TrackingController
from .execution import LinkedExecution


class ConnectionError(ValueError):
    pass


class ConnectionService:
    def __init__(
        self,
        settings_dir=None,
        driver_factory=SerialDriver,
        camera_service=None,
        bridge_factory=GymBridge,
        start_worker=True,
    ):
        self.settings_dir = Path(
            settings_dir
            or os.environ.get(
                "SO101_SETTINGS_DIR", Path.home() / ".config" / "so101-studio"
            )
        )
        self.driver_factory = driver_factory
        self.bridge_factory = bridge_factory
        self.lock = threading.RLock()
        self.execution = LinkedExecution(self)
        self._real_cancel = threading.Event()
        self._preparing = False
        self.recovering = False
        self.manual = None
        self.control_epoch = secrets.randbits(48)
        self.driver = None
        self.bridge = None
        self.connected = False
        self.identity = None
        self.port = None
        self.robot_port = None
        self.owner_session_id = None
        self.enabled = False
        self.sync_mode = "off"
        self.fault = None
        self.telemetry = []
        self.measured_at = 0.0
        self.target_rad = None
        self.tracker = None
        self.desired_rad = None
        self.lease_until = 0.0
        self.last_command = 0.0
        self.last_jog = 0.0
        self.calibration = None
        self.assignments = {"back": None, "front": None, "wrist": None}
        self._exit = threading.Event()
        self.worker = None
        if camera_service is None:
            from .cameras import CameraService

            camera_service = CameraService()
        self.cameras = camera_service
        try:
            data = json.loads((self.settings_dir / "connection.json").read_text())
            self.assignments = Assignments.model_validate(
                data.get("assignments", {})
            ).model_dump()
            if data.get("robot_port"):
                self.robot_port = RobotPort(port=data["robot_port"]).port
            if data.get("calibration"):
                self.calibration = Calibration.model_validate(data["calibration"])
        except FileNotFoundError:
            pass
        except Exception as exc:
            self.fault = "Settings could not be loaded: " + str(exc)
        if start_worker:
            self.worker = threading.Thread(
                target=self._loop, daemon=True, name="so101-connection"
            )
            self.worker.start()

    @property
    def calibrated(self):
        return bool(
            self.connected
            and self.calibration
            and self.calibration.confirmed
            and self.calibration.identity == self.identity
        )

    def settings(self):
        with self.lock:
            return {
                "calibration": (
                    self.calibration.model_dump() if self.calibration else None
                ),
                "assignments": dict(self.assignments),
                "robot_port": self.robot_port,
            }

    def configure_port(self, port):
        port = RobotPort(port=port).port
        with self.lock:
            if self.connected and port != self.port:
                raise ConnectionError(
                    "Disconnect the robot in Gym before changing its port"
                )
            previous = self.robot_port
            self.robot_port = port
            try:
                self._persist()
            except Exception:
                self.robot_port = previous
                raise
            return self.settings()

    def verify(self):
        # Never create a Gym owner, enable torque, or send goals. Do not hold
        # the serial lock while camera workers run: stop/heartbeat must remain responsive.
        with self.lock:
            assignments = dict(self.assignments)
            port = self.robot_port
            robot = dict(ok=False, port=port, motor_count=0, calibrated=False)
            temporary = None
            try:
                if not port:
                    raise ConnectionError("Save a serial port first")
                if self.connected:
                    if port != self.port:
                        raise ConnectionError(
                            "Connected robot does not match the saved port"
                        )
                    self._read()
                    rows, identity = self.telemetry, self.identity
                else:
                    temporary = self.driver_factory(port)
                    temporary.open()
                    rows = temporary.read()
                    self._validate_rows(rows)
                    identity = temporary.identity
                robot.update(
                    ok=True,
                    motor_count=len(rows),
                    identity=identity,
                    calibrated=bool(
                        self.calibration
                        and self.calibration.confirmed
                        and self.calibration.identity == identity
                    ),
                    message="All six motors responded. No movement requested.",
                )
            except Exception as exc:
                robot["message"] = str(exc)
            finally:
                if temporary is not None:
                    temporary.close()
        cameras = [
            dict(self.cameras.snapshot(index), role=role)
            for role, index in assignments.items()
            if index is not None
        ]
        unassigned = [role for role, index in assignments.items() if index is None]
        return dict(
            robot=robot,
            cameras=cameras,
            unassigned=unassigned,
            ok=robot["ok"] and all(c["available"] for c in cameras),
        )

    def scene_command(self, session, command):
        if command.type == "real_run":
            return self.run_real(session)
        with self.lock:
            owns_robot = self.connected and self.owner_session_id == session.id
            if owns_robot and command.type in {
                "run",
                "pause",
                "stop",
                "physics",
                "plan",
                "step",
            }:
                self._real_cancel.set()
                if self.enabled or self.sync_mode != "off":
                    self.stop(session.id)
            # A simulation command never enables or follows physical hardware.
            return session.execute(command)

    def run_real(self, session):
        from ...planning import clone_simulation, calculate_plan
        from ...sessions import Command
        import mujoco

        with self.lock, session.lock:
            self._owner(session.id)
            self._calibrated()
            if self._preparing or session.sim.running or self.execution.active:
                raise ConnectionError(
                    "Stop the current run before starting the real robot"
                )
            approved = session.successful_trial
            if approved is None:
                raise ConnectionError(
                    "Run a successful simulation before Run Realrobot"
                )
            if self.enabled or self.sync_mode != "off":
                self.stop(session.id)
            q = self._read()
            self._validate(q, q)
            trial = clone_simulation(approved)
            trial.data.qpos[:6] = q
            trial.data.qvel[:6] = 0
            trial.data.ctrl[:6] = q
            mujoco.mj_forward(trial.model, trial.data)
            cancel = self._real_cancel = threading.Event()
            self._preparing = True
            self.lease_until = time.monotonic() + 3
            self.execution.phase = "preparing"
            self.execution.message = (
                "Checking the successful task from measured arm angles."
            )
        try:
            plan = calculate_plan(trial, cancel)
            with self.lock, session.lock:
                if (
                    cancel.is_set()
                    or time.monotonic() > self.lease_until
                    or session.closed
                    or session.successful_trial is not approved
                ):
                    raise ConnectionError(
                        "Real robot preparation cancelled; run simulation again"
                    )
                self._owner(session.id)
                if not plan.get("verified"):
                    raise ConnectionError(
                        "Physical start rehearsal: " + plan["message"]
                    )
                current = self._read()
                self._validate(current, current)
                if max(abs(a - b) for a, b in zip(current, q)) > 0.01:
                    raise ConnectionError(
                        "Arm moved during preparation; retry Run Realrobot"
                    )
                trial.scene.cameras = session.sim.scene.cameras
                trial.revision = session.sim.revision + 1
                session.sim = trial
                session.plan = plan
                session.sequence += 1
                session.trial_start = None
                # A physical attempt consumes this approval: object positions
                # may change even if the attempt later stops part-way through.
                session.successful_trial = None
                self._preparing = False
                result = self.execution.start(session, Command(type="run"))
                session.broadcast(result)
                return result
        except Exception as exc:
            with self.lock:
                self.execution.phase = "paused"
                self.execution.message = str(exc)
            raise
        finally:
            with self.lock:
                self._preparing = False

    def replace_scene(self, session, command):
        # Same lock order as the streaming worker: hardware before Gym session.
        # Keep the lock until the replacement is complete, preventing a concurrent enable.
        with self.lock:
            owns_robot = self.connected and self.owner_session_id == session.id
            if owns_robot:
                self._real_cancel.set()
            if owns_robot and (self.enabled or self.sync_mode != "off"):
                self.stop(session.id)
            result = session.execute(command)
            if owns_robot:
                self.execution = LinkedExecution(self)
            return result

    def _persist(self):
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        fd, path = tempfile.mkstemp(
            prefix="connection-", suffix=".json", dir=self.settings_dir
        )
        try:
            with os.fdopen(fd, "w") as out:
                json.dump(self.settings(), out, indent=2)
                out.flush()
                os.fsync(out.fileno())
            os.replace(path, self.settings_dir / "connection.json")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def status(self):
        with self.lock:
            rows = [
                dict(
                    row,
                    name=JOINT_NAMES[i],
                    position_rad=(
                        self._angle(i, row["raw"]) if self.calibrated else None
                    ),
                )
                for i, row in enumerate(self.telemetry)
            ]
            limits, preview, mount = None, None, None
            if self.connected and self.calibrated and len(rows) == 6:
                try:
                    limits = self._control_limits()
                    if hasattr(self.bridge, "mount"):
                        mount = self.bridge.mount()
                    if hasattr(self.bridge, "preview"):
                        preview = self.bridge.preview([r["position_rad"] for r in rows])
                except (ValueError, KeyError, ConnectionError):
                    # A removed scene must not make Stop/Disconnect status unreadable.
                    pass
            return dict(
                connected=self.connected,
                gym_execution=self.execution.status(),
                control_epoch=self.control_epoch,
                manual_phase=self.manual.phase if self.manual else None,
                manual_target=list(self.manual.target) if self.manual else None,
                control_limits=limits,
                limit_violations=[
                    dict(
                        name=row["name"],
                        angle_rad=row["position_rad"],
                        min_rad=lo,
                        max_rad=hi,
                        raw=row["raw"],
                        raw_min=self.calibration.joints[i].raw_min,
                        raw_max=self.calibration.joints[i].raw_max,
                    )
                    for i, (row, (lo, hi)) in enumerate(zip(rows, limits or []))
                    if not lo <= row["position_rad"] <= hi
                ],
                robot_preview=preview,
                robot_mount=mount,
                port=self.port,
                identity=self.identity,
                owner_session_id=self.owner_session_id,
                enabled=self.enabled,
                sync_mode=self.sync_mode,
                fault=self.fault,
                calibrated=self.calibrated,
                calibration=self.calibration.model_dump() if self.calibration else None,
                telemetry=rows,
                telemetry_age_s=(
                    max(0, time.monotonic() - self.measured_at)
                    if self.measured_at
                    else None
                ),
                target_rad=self.target_rad,
                desired_rad=self.desired_rad,
                tracking_error_rad=(
                    [r["position_rad"] - q for r, q in zip(rows, self.desired_rad)]
                    if self.calibrated and self.desired_rad and len(rows) == 6
                    else None
                ),
                compensation_rad=list(self.tracker.bias) if self.tracker else None,
                temperature_rechecks=getattr(self.driver, "temperature_rechecks", 0),
                last_temperature_check=getattr(
                    self.driver, "last_temperature_check", None
                ),
                lease_remaining_s=max(0, self.lease_until - time.monotonic()),
            )

    def _owner(self, session_id):
        if not self.connected:
            raise ConnectionError("Connect the arm first")
        if session_id != self.owner_session_id:
            raise ConnectionError("Hardware is owned by another Gym session")
        try:
            self.bridge.check_alive()
        except Exception as exc:
            raise ConnectionError(str(exc)) from exc

    def connect(self, port, session_id, registry):
        with self.lock:
            if self.connected:
                raise ConnectionError(
                    "Disconnect the current owner before reconnecting"
                )
            bridge = self.bridge_factory(registry, session_id)
            driver = self.driver_factory(port)
            try:
                driver.open()
                rows = driver.read()
                self._validate_rows(rows)
            except Exception as exc:
                driver.close()
                raise ConnectionError(str(exc)) from exc
            self.execution = LinkedExecution(self)
            self.driver = driver
            self.bridge = bridge
            self.port = port
            self.identity = driver.identity
            self.owner_session_id = session_id
            self.connected = True
            self.enabled = False
            self.sync_mode = "off"
            self.fault = None
            self.telemetry = rows
            self.measured_at = time.monotonic()
            self.target_rad = None
            self.tracker = None
            self.desired_rad = None
            return self.status()

    def _validate_rows(self, rows):
        if (
            len(rows) != 6
            or [r["id"] for r in rows] != list(range(1, 7))
            or any(r["model"] != 777 for r in rows)
        ):
            raise ConnectionError("All six verified STS3215 motors are required")
        for row in rows:
            if (
                not math.isfinite(row["raw"])
                or not 0 <= row["raw"] <= 4095
                or row["raw"] != int(row["raw"])
                or not 4 <= row["voltage"] <= 14
                or row["temperature"] >= 65
            ):
                raise ConnectionError(
                    "Unsafe motor encoder, voltage or temperature telemetry: "
                    f"motor {row['id']}, raw={row['raw']}, "
                    f"voltage={row['voltage']}, temperature={row['temperature']}"
                )

    def _read(self):
        started = time.monotonic()
        rows = self.driver.read()
        self._validate_rows(rows)
        if time.monotonic() - started > 1:
            raise ConnectionError("Stale telemetry: serial read exceeded one second")
        self.telemetry = rows
        self.measured_at = time.monotonic()
        return (
            [self._angle(i, r["raw"]) for i, r in enumerate(rows)]
            if self.calibrated
            else None
        )

    def _angle(self, i, raw):
        c = self.calibration.joints[i]
        return (raw - c.zero_raw) * c.direction * c.radians_per_tick

    def _raw(self, q):
        values = []
        for angle, c in zip(q, self.calibration.joints):
            if not math.isfinite(angle):
                raise ConnectionError(
                    f"Invalid angle for {c.name}: finite radians required"
                )
            raw = round(c.zero_raw + angle / (c.direction * c.radians_per_tick))
            if not c.raw_min <= raw <= c.raw_max:
                raise ConnectionError(
                    f"Calibrated raw encoder limit exceeded: {c.name} "
                    f"at {math.degrees(angle):.2f} degrees (raw {raw}); "
                    f"allowed raw {c.raw_min}..{c.raw_max}. "
                    "Reposition the arm within its verified range or review "
                    "the joint calibration before requesting motion."
                )
            values.append(raw)
        return values

    def _control_limits(self):
        limits = []
        for i, (lo, hi) in enumerate(self.bridge.limits()):
            c = self.calibration.joints[i]
            raw_lo, raw_hi = sorted(
                (self._angle(i, c.raw_min), self._angle(i, c.raw_max))
            )
            limits.append((max(lo, raw_lo), min(hi, raw_hi)))
        return limits

    def _calibrated(self):
        if not self.calibrated:
            raise ConnectionError(
                "Confirmed calibration for this verified device identity is required"
            )

    def _validate(self, start, end):
        self._raw(start)
        self._raw(end)
        try:
            self.bridge.validate(start, end)
        except Exception as exc:
            raise ConnectionError(str(exc)) from exc

    def save_calibration(self, value):
        with self.lock:
            self._owner(value.session_id)
            if self._preparing:
                raise ConnectionError(
                    "Stop real-run preparation before changing robot controls"
                )
            if self.enabled or self.sync_mode != "off":
                raise ConnectionError(
                    "Stop motion and synchronization before editing calibration"
                )
            if value.identity != self.identity:
                raise ConnectionError(
                    "Calibration identity does not match connected device"
                )
            self.calibration = value
            self.tracker = None
            self.desired_rad = None
            self._persist()
            return self.status()

    def move(self, session_id, joints=None, preset=None, control_epoch=None):
        from .controls import move

        return move(self, session_id, joints, preset, control_epoch)

    def torque_control(self, session_id, enabled, control_epoch=None):
        from .controls import torque

        return torque(self, session_id, enabled, control_epoch)

    def retreat(self, session_id):
        from .retreat import retreat

        return retreat(self, session_id)

    def align(self, session_id):
        with self.lock:
            self._owner(session_id)
            if self._preparing:
                raise ConnectionError(
                    "Stop real-run preparation before changing robot controls"
                )
            self._calibrated()
            if self.enabled or self.sync_mode != "off":
                raise ConnectionError(
                    "Stop motion and synchronization before aligning Gym"
                )
            q = self._read()
            self._validate(q, q)
            self.bridge.set(q)
            return self.status()

    def enable(self, session_id):
        with self.lock:
            self._owner(session_id)
            if self._preparing:
                raise ConnectionError(
                    "Stop real-run preparation before changing robot controls"
                )
            self._calibrated()
            if self.enabled or self.sync_mode != "off":
                raise ConnectionError(
                    "Stop the current motion or synchronization before enabling"
                )
            q = self._read()
            self._validate(q, q)
            if self.tracker is None:
                self.tracker = TrackingController(q, limits=self._control_limits())
            else:
                self.tracker.default_rates()
                self.tracker.reset(q, preserve_bias=True)
            hold = list(self.tracker.output)
            self._validate(q, hold)
            # Stage the current pose plus validated hold bias before enabling torque.
            try:
                self.driver.goals(self._raw(hold))
                self.driver.torque(
                    [
                        max(1, math.floor(0.3 / c.radians_per_tick))
                        for c in self.calibration.joints
                    ]
                )
            except Exception as exc:
                self._fault(str(exc), hold=False)
                raise ConnectionError(str(exc)) from exc
            self.last_jog = 0.0
            self.target_rad = hold
            self.desired_rad = list(q)
            self.enabled = True
            self.fault = None
            self.last_command = time.monotonic()
            self.lease_until = time.monotonic() + 3
            return self.status()

    def heartbeat(self, session_id):
        with self.lock:
            self._owner(session_id)
            if self._preparing and time.monotonic() > self.lease_until:
                self._fault("Controller heartbeat expired during preparation")
                raise ConnectionError(self.fault)
            self.lease_until = time.monotonic() + 3
            return self.status()

    def _hold(self, preserve_compensation=False):
        if self.enabled and self.calibrated:
            q = self._read()
            hold = list(q)
            if (
                not preserve_compensation
                and self.target_rad
                and max(abs(a - b) for a, b in zip(q, self.target_rad)) <= 0.05
            ):
                try:
                    self.bridge.validate(self.target_rad, self.target_rad)
                    hold = list(self.target_rad)
                except Exception:
                    pass
            if preserve_compensation and self.tracker:
                self.tracker.reset(q, preserve_bias=True)
                candidate = list(self.tracker.output)
                try:
                    self._validate(q, candidate)
                    hold = candidate
                except Exception:
                    self.tracker.reset(q)
            if time.monotonic() - self.measured_at > 0.2:
                q = self._read()
                hold = list(q)
                self.tracker = None
            self.driver.goals(self._raw(hold))
            self.target_rad = hold
            self.desired_rad = list(q)

    def _fault(self, message, hold=True, preserve_compensation=False):
        self.control_epoch += 1
        self.manual = None
        self.recovering = False
        self._real_cancel.set()
        self.execution.halt(message)
        try:
            if hold:
                self._hold(preserve_compensation)
        except Exception as exc:
            message += "; hold could not be confirmed: " + str(exc)
            preserve_compensation = False
        self.enabled = False
        self.sync_mode = "off"
        self.fault = message
        if not preserve_compensation:
            self.tracker = None

    def stop(self, session_id):
        with self.lock:
            # The owner can stop after its Gym session is deleted.
            if session_id != self.owner_session_id:
                raise ConnectionError("Hardware is owned by another Gym session")
            self._fault(
                "Stopped; existing motor torque is preserved",
                hold=True,
                preserve_compensation=True,
            )
            return self.status()

    def disconnect(self, session_id):
        with self.lock:
            if session_id != self.owner_session_id:
                raise ConnectionError("Hardware is owned by another Gym session")
            self._fault(
                "Disconnected; existing motor torque is preserved",
                hold=True,
                preserve_compensation=True,
            )
            try:
                if self.driver:
                    self.driver.close()
            finally:
                self.driver = None
                self.connected = False
                self.owner_session_id = None
                self.telemetry = []
                self.measured_at = 0
            return self.status()

    def jog(self, session_id, joint, delta_rad):
        with self.lock:
            self._owner(session_id)
            if self.manual is not None:
                raise ConnectionError(
                    "Stop manual movement before jogging or synchronization"
                )
            self._calibrated()
            if not self.enabled:
                raise ConnectionError("Explicitly enable motion first")
            if self.sync_mode != "off":
                raise ConnectionError("Stop synchronization before jogging")
            if (
                not 0 <= joint < 6
                or not math.isfinite(delta_rad)
                or abs(delta_rad) > 0.05
            ):
                raise ConnectionError("Jog is bounded to ±0.05 radians")
            if time.monotonic() > self.lease_until:
                self._fault("Controller heartbeat expired")
                raise ConnectionError(self.fault)
            q = self._read()
            if (
                self.target_rad
                and max(abs(a - b) for a, b in zip(q, self.target_rad)) > 0.15
            ):
                self._fault("Motor tracking error")
                raise ConnectionError(self.fault)
            target = list(q)
            target[joint] += delta_rad
            # Never allow rapid repeated requests to exceed 0.3 rad/s; one initial 0.05 rad jog is allowed.
            allowance = min(
                0.05, max(0, time.monotonic() - self.last_jog) * 0.3 + 0.001
            )
            if abs(delta_rad) > allowance:
                raise ConnectionError("Jog velocity limit; wait for measured feedback")
            self._validate(q, target)
            try:
                self.driver.goals(self._raw(target))
            except Exception as exc:
                self._fault(str(exc), hold=False)
                raise ConnectionError(str(exc)) from exc
            self.target_rad = target
            self.last_command = time.monotonic()
            self.last_jog = self.last_command
            return self.status()

    def sync(self, session_id, mode):
        with self.lock:
            self._owner(session_id)
            if self.manual is not None:
                raise ConnectionError(
                    "Stop manual movement before jogging or synchronization"
                )
            if mode == "off":
                return self.stop(session_id)
            if self._preparing:
                raise ConnectionError(
                    "Stop real-run preparation before changing robot controls"
                )
            if mode not in ("real_to_gym", "gym_to_real"):
                raise ConnectionError("Unknown sync mode")
            self._calibrated()
            q = self._read()
            self._validate(q, q)
            if mode == "gym_to_real":
                if not self.enabled:
                    raise ConnectionError("Explicitly enable motion first")
                if max(abs(a - b) for a, b in zip(q, self.bridge.get())) > 0.15:
                    raise ConnectionError(
                        "Initial Gym/arm pose difference exceeds 0.15 radians"
                    )
            elif self.enabled:
                raise ConnectionError(
                    "Stop motion before enabling read-only real-to-Gym synchronization"
                )
            self.sync_mode = mode
            if self.tracker is None:
                self.tracker = TrackingController(q, limits=self._control_limits())
            else:
                self.tracker.default_rates()
                self.tracker.reset(q, preserve_bias=True)
            self.target_rad = list(self.tracker.output)
            self.desired_rad = list(q)
            self.last_command = time.monotonic()
            self.lease_until = time.monotonic() + 3
            self.fault = None
            return self.status()

    def tick(self):
        with self.lock:
            if self.recovering:
                return
            if not self.connected:
                return
            fresh = False
            try:
                q = self._read()
                fresh = True
                self.bridge.check_alive()
                if self._preparing and time.monotonic() > self.lease_until:
                    self._fault("Controller heartbeat expired during preparation")
                    return
                if self.manual is not None:
                    if time.monotonic() > self.lease_until:
                        self._fault("Controller heartbeat expired")
                        return
                    self.manual.tick(q)
                    return
                if self.enabled or self.sync_mode != "off":
                    if time.monotonic() > self.lease_until:
                        self._fault("Controller heartbeat expired")
                        return
                    self._calibrated()
                    self._validate(q, q)
                if (
                    self.enabled
                    and self.target_rad
                    and max(abs(a - b) for a, b in zip(q, self.target_rad)) > 0.15
                ):
                    self._fault("Motor tracking error exceeds 0.15 radians")
                    return
                if self.sync_mode == "real_to_gym":
                    self.bridge.set(q)
                elif self.sync_mode == "gym_to_real":
                    if self.execution.active:
                        self.execution.advance(q)
                        if self.sync_mode != "gym_to_real":
                            return
                    desired = self.bridge.get()
                    dt = max(0.001, time.monotonic() - self.last_command)
                    # Reject a changed/reloaded Gym scene that would otherwise make a large physical move.
                    if max(abs(a - b) for a, b in zip(q, desired)) > 0.3:
                        raise ConnectionError("Gym target jumped beyond 0.3 radians")
                    self.desired_rad = list(desired)
                    target = self.tracker.step(
                        desired,
                        q,
                        dt,
                        [c.radians_per_tick for c in self.calibration.joints],
                    )
                    if max(abs(a - b) for a, b in zip(q, target)) > 0.15:
                        raise ConnectionError(
                            "Motor tracking error: command lead exceeds 0.15 radians"
                        )
                    self._validate(q, target)
                    if time.monotonic() - self.measured_at > 0.2:
                        raise ConnectionError(
                            "Stale feedback after collision validation"
                        )
                    self.driver.goals(self._raw(target))
                    self.target_rad = target
                    self.last_command = time.monotonic()
            except Exception as exc:
                self._fault(str(exc), hold=fresh)

    def _loop(self):
        while not self._exit.wait(0.05):
            self.tick()

    def assign_cameras(self, assignments):
        with self.lock:
            self.assignments = Assignments.model_validate(assignments).model_dump()
            self._persist()
            return self.settings()

    def shutdown(self):
        self._exit.set()
        if self.worker:
            self.worker.join(timeout=3)
        with self.lock:
            if self.connected:
                self.disconnect(self.owner_session_id)
        self.cameras.shutdown()
