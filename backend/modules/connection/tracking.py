"""Bounded outer position loop; calibration stays independent of load correction."""

import math


def clamp(value, limit):
    return max(-limit, min(limit, value))


class TrackingController:
    MAX_SPEED = 0.3
    MAX_ACCELERATION = 1.2
    MAX_BIAS = 0.1
    MAX_CORRECTION = 0.12
    PROPORTIONAL_GAIN = 0.8
    INTEGRAL_GAIN = 1.2

    def __init__(self, measured):
        self.bias = [0.0] * 6
        self.reset(measured)

    def reset(self, measured, *, preserve_bias=False):
        if not preserve_bias:
            self.bias = [0.0] * 6
        self.reference = list(measured)
        self.output = [q + b for q, b in zip(measured, self.bias)]
        self.velocity = [0.0] * 6

    def step(self, desired, measured, dt, resolution):
        if not math.isfinite(dt) or not 0 < dt <= 0.2:
            raise ValueError(
                "Stale control cycle; stop before resuming synchronization"
            )
        if any(len(v) != 6 for v in (desired, measured, resolution)) or not all(
            math.isfinite(v)
            for values in (desired, measured, resolution)
            for v in values
        ):
            raise ValueError("Six finite joint measurements and targets are required")
        for i in range(6):
            # Reserve part of the output speed for gentle feedback corrections.
            reference = self.reference[i] + clamp(
                desired[i] - self.reference[i], 0.24 * dt
            )
            error = reference - measured[i]
            candidate = self.bias[i]
            if abs(error) > max(0.003, 2 * resolution[i]):
                candidate = clamp(
                    candidate + clamp(self.INTEGRAL_GAIN * error, 0.04) * dt,
                    self.MAX_BIAS,
                )
            correction = clamp(
                candidate + self.PROPORTIONAL_GAIN * error, self.MAX_CORRECTION
            )
            wanted = reference + correction
            distance = wanted - self.output[i]
            braking_speed = math.sqrt(2 * self.MAX_ACCELERATION * abs(distance))
            velocity = clamp(distance / dt, min(self.MAX_SPEED, braking_speed))
            velocity = self.velocity[i] + clamp(
                velocity - self.velocity[i], self.MAX_ACCELERATION * dt
            )
            output = self.output[i] + velocity * dt
            # Do not integrate farther into output rate saturation.
            if (wanted - output) * (candidate - self.bias[i]) <= 0 or abs(
                wanted - output
            ) < 0.003:
                self.bias[i] = candidate
            self.reference[i] = reference
            self.output[i] = output
            self.velocity[i] = velocity
        return list(self.output)
