"""Bounded-memory comparison of measured joints and simultaneous Gym poses."""

import math
import time
import uuid
from .schemas import JOINT_NAMES


class EpisodeReport:
    def __init__(self, session_id):
        self.id = uuid.uuid4().hex
        self.session_id = session_id
        self.started = time.monotonic()
        self.count = 0
        self.squared = [0.0] * 6
        self.maximum = [0.0] * 6
        self.last = None

    def observe(self, measured, reference, sim_time):
        if len(measured) != 6 or len(reference) != 6 or not all(
            math.isfinite(v) for values in (measured, reference, [sim_time]) for v in values
        ):
            raise ValueError("Episode report requires six finite measured and Gym angles")
        for i, (actual, expected) in enumerate(zip(measured, reference)):
            error = actual - expected
            self.squared[i] += error * error
            self.maximum[i] = max(self.maximum[i], abs(error))
        self.count += 1
        self.last = (list(measured), list(reference), sim_time, time.monotonic())

    def finish(self, outcome, reason):
        now = time.monotonic()
        joints = []
        if self.last:
            measured, reference, _, _ = self.last
            for i, name in enumerate(JOINT_NAMES):
                joints.append(dict(
                    name=name,
                    rmse_deg=math.degrees(math.sqrt(self.squared[i] / self.count)),
                    max_abs_error_deg=math.degrees(self.maximum[i]),
                    last_error_deg=math.degrees(measured[i] - reference[i]),
                    last_measured_deg=math.degrees(measured[i]),
                    last_gym_deg=math.degrees(reference[i]),
                ))
        return dict(
            id=self.id,
            session_id=self.session_id,
            outcome=outcome,
            reason=reason,
            samples=self.count,
            duration_s=now - self.started,
            simulation_time_s=self.last[2] if self.last else None,
            last_sample_age_s=now - self.last[3] if self.last else None,
            joints=joints,
        )
