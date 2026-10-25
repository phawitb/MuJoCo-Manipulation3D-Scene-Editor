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
    VELOCITY_FEEDFORWARD = 0.12
    VELOCITY_FILTER_SECONDS = 0.1

    def __init__(self, measured, *, limits=None):
        self.limits = limits or [(-math.inf, math.inf)] * 6
        self.bias = [0.0] * 6
        self.reset(measured)

    def reset(self, measured, *, preserve_bias=False):
        if not preserve_bias:
            self.bias = [0.0] * 6
        self.reference = list(measured)
        self.output = [
            max(lo, min(hi, q + b))
            for q, b, (lo, hi) in zip(measured, self.bias, self.limits)
        ]
        self.velocity = [0.0] * 6
        self.reference_velocity = [0.0] * 6

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
        if any(not lo <= q <= hi for q, (lo, hi) in zip(desired, self.limits)):
            raise ValueError("Requested target exceeds joint limit")
        for i in range(6):
            # Reserve part of the output speed for gentle feedback corrections.
            reference = self.reference[i] + clamp(
                desired[i] - self.reference[i], 0.24 * dt
            )
            # A filtered reference velocity compensates servo lag without
            # differentiating noisy encoder readings. Existing correction and
            # output speed/acceleration limits also bound this feedforward.
            reference_speed = (reference - self.reference[i]) / dt
            blend = dt / (self.VELOCITY_FILTER_SECONDS + dt)
            self.reference_velocity[i] += blend * (
                reference_speed - self.reference_velocity[i]
            )
            error = reference - measured[i]
            candidate = self.bias[i]
            if abs(error) > max(0.003, 2 * resolution[i]):
                candidate = clamp(
                    candidate + clamp(self.INTEGRAL_GAIN * error, 0.04) * dt,
                    self.MAX_BIAS,
                )
            correction = clamp(
                candidate
                + self.PROPORTIONAL_GAIN * error
                + self.VELOCITY_FEEDFORWARD * self.reference_velocity[i],
                self.MAX_CORRECTION,
            )
            wanted = reference + correction
            lo, hi = self.limits[i]
            # Keep rounded encoder goals inside the physical/model intersection.
            lower, upper = lo + resolution[i] * 0.51, hi - resolution[i] * 0.51
            bounded_wanted = max(lower, min(upper, wanted))
            distance = bounded_wanted - self.output[i]
            braking_speed = math.sqrt(2 * self.MAX_ACCELERATION * abs(distance))
            velocity = clamp(distance / dt, min(self.MAX_SPEED, braking_speed))

            # Reserve stopping distance for the longest accepted cycle (200 ms),
            # including its discrete step. This brakes before output saturation.
            def safe_speed(distance):
                reserve = self.MAX_ACCELERATION * 0.2
                return (
                    math.sqrt(reserve**2 + 2 * self.MAX_ACCELERATION * max(0, distance))
                    - reserve
                )

            velocity = max(
                -safe_speed(self.output[i] - lower),
                min(safe_speed(upper - self.output[i]), velocity),
            )
            velocity = self.velocity[i] + clamp(
                velocity - self.velocity[i], self.MAX_ACCELERATION * dt
            )
            output = self.output[i] + velocity * dt
            if not lo <= output <= hi:
                raise ValueError("Controller cannot brake within joint limits")
            # Do not integrate farther into position or rate saturation.
            if (wanted - output) * (candidate - self.bias[i]) <= 0 or abs(
                wanted - output
            ) < 0.003:
                self.bias[i] = candidate
            self.reference[i] = reference
            self.output[i] = output
            self.velocity[i] = velocity
        return list(self.output)
