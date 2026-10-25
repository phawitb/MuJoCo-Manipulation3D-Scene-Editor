"""Tool endpoint feedback; no claim of independently observed object success."""

import math
import time
import uuid


class EpisodeReport:
    def __init__(self, session_id):
        self.id = uuid.uuid4().hex
        self.session_id = session_id
        self.started = time.monotonic()
        self.count = 0
        self.last = None
        self.maximum = 0.0
        self.squared = 0.0
        self.sample_at = None

    def observe(self, error):
        if any(
            not math.isfinite(error[k]) or error[k] < 0
            for k in ("position_mm", "orientation_deg", "opening_deg")
        ):
            raise ValueError("Finite nonnegative endpoint errors required")
        self.count += 1
        self.last = dict(error)
        self.maximum = max(self.maximum, error["position_mm"])
        self.squared += error["position_mm"] ** 2
        self.sample_at = time.monotonic()

    def finish(self, outcome, reason):
        now = time.monotonic()
        return dict(
            id=self.id,
            session_id=self.session_id,
            outcome=outcome,
            reason=reason,
            measurement_source="encoder_fk",
            object_verified=False,
            environment_source="simulation_rehearsal",
            samples=self.count,
            duration_s=now - self.started,
            last_sample_age_s=(
                now - self.sample_at if self.sample_at is not None else None
            ),
            last_error=self.last,
            peak_target_distance_mm=self.maximum,
            rms_target_distance_mm=(
                math.sqrt(self.squared / self.count) if self.count else None
            ),
        )
