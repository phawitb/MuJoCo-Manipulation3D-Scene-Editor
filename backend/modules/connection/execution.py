"""Feedback-paced Gym policy execution. The service owns the hardware lock."""

import time


class LinkedExecution:
    # Leave headroom below the existing tracking/jump limits. Physics dt stays
    # unchanged; only the number of physics steps per measured update changes.
    MAX_LEAD = 0.035
    MAX_ADVANCE = 0.006
    MAX_STEPS = 10

    def __init__(self, service):
        self.service = service
        self.session = None
        self.phase = "idle"
        self.message = ""
        self.last_progress = 0.0
        self.settling_since = None
        self.settled_frames = 0

    @property
    def active(self):
        return self.session is not None

    def status(self):
        return dict(
            phase=self.phase,
            message=self.message,
            session_id=self.session.id if self.session else None,
        )

    def start(self, session, command):
        service = self.service
        with session.lock:
            if self.session is session and session.sim.running:
                return session.packet()
            session.validate_run()
            q = service._read()
            service._validate(q, q)
            if max(abs(a - b) for a, b in zip(q, session.sim.data.qpos[:6])) > 0.04:
                raise ValueError(
                    "Real arm moved since calculation. Stop the task and calculate again from its measured pose."
                )
            if service.enabled or service.sync_mode != "off":
                service.stop(session.id)
            try:
                service.enable(session.id)
                service.sync(session.id, "gym_to_real")
                self.session = session
                session.external_clock = True
                self.phase = "running"
                self.message = (
                    "Real arm follows Gym; simulation waits for measured feedback."
                )
                self.last_progress = time.monotonic()
                self.settling_since = None
                self.settled_frames = 0
                return session.execute(command)
            except Exception:
                service._fault("Connected Run could not start")
                raise

    def halt(self, message):
        session, self.session = self.session, None
        if session is None:
            return
        with session.lock:
            session.sim.running = False
            session.external_clock = False
            self.phase = "paused"
            self.message = message
            session.broadcast(session.packet())

    def advance(self, measured):
        session = self.session
        if session is None:
            return
        with session.lock:
            if session.closed:
                raise ValueError("Gym session closed during connected Run")
            sim = session.sim
            if sim.policy.status not in {"running", "succeeded"}:
                raise ValueError("Gym task stopped: " + sim.policy.message)
            error = max(abs(a - b) for a, b in zip(measured, sim.data.qpos[:6]))
            if not sim.running:
                if sim.policy.status != "succeeded":
                    raise ValueError("Gym task stopped: " + sim.policy.message)
                if self.settling_since is None:
                    self.settling_since = time.monotonic()
                self.settled_frames = self.settled_frames + 1 if error <= 0.015 else 0
                if self.settled_frames >= 5:
                    self.session = None
                    session.external_clock = False
                    self.phase = "completed"
                    self.message = (
                        "Gym task succeeded and real arm reached the final joint pose."
                    )
                    self.service.stop(session.id)
                elif time.monotonic() - self.settling_since > 8:
                    raise ValueError("Real arm did not settle at the final Gym pose")
                return
            if error > self.MAX_LEAD:
                self.phase = "waiting"
                self.message = "Waiting for the real arm to reach the current Gym pose."
                if time.monotonic() - self.last_progress > 10:
                    raise ValueError(
                        "Real arm cannot follow the Gym pose; connected Run paused"
                    )
                return
            self.phase = "running"
            self.message = (
                "Real arm follows Gym; simulation waits for measured feedback."
            )
            start = sim.data.qpos[:6].copy()
            packet = None
            for _ in range(self.MAX_STEPS):
                packet = session.tick(1, external=True)
                if sim.policy.status not in {"running", "succeeded"}:
                    raise ValueError("Gym task stopped: " + sim.policy.message)
                if (
                    not sim.running
                    or max(abs(a - b) for a, b in zip(start, sim.data.qpos[:6]))
                    >= self.MAX_ADVANCE
                ):
                    break
                if (
                    max(abs(a - b) for a, b in zip(measured, sim.data.qpos[:6]))
                    >= self.MAX_LEAD
                ):
                    break
            self.last_progress = time.monotonic()
            if packet:
                session.broadcast(packet)
