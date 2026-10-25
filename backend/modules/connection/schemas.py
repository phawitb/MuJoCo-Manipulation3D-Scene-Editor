"""Strict local hardware request types; all joint angles are radians."""

import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

JOINT_NAMES = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Owner(StrictModel):
    session_id: str = Field(min_length=1, max_length=100)


class RobotPort(StrictModel):
    port: str = Field(
        min_length=1, max_length=200, pattern=r"^/dev/(cu\.|tty)[A-Za-z0-9_.-]+$"
    )


class Connect(Owner, RobotPort):
    pass


class JointCalibration(StrictModel):
    name: Literal[
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
        "gripper",
    ]
    # Midpoints of integer encoder limits can be half ticks.
    zero_raw: float = Field(ge=-32767, le=32767)
    direction: Literal[-1, 1]
    raw_min: int = Field(ge=0, le=4095)
    raw_max: int = Field(ge=0, le=4095)
    radians_per_tick: float = Field(default=math.tau / 4096, gt=0, le=0.1)

    @model_validator(mode="after")
    def ordered(self):
        if self.raw_min >= self.raw_max:
            raise ValueError("Raw minimum must be below maximum")
        return self


class Calibration(Owner):
    identity: str = Field(min_length=1, max_length=1000)
    confirmed: Literal[True]
    joints: list[JointCalibration] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def names(self):
        if tuple(j.name for j in self.joints) != JOINT_NAMES:
            raise ValueError("Use all six joints in motor ID order")
        return self


class Jog(Owner):
    joint: int = Field(ge=0, le=5)
    delta_rad: float = Field(ge=-0.05, le=0.05)


class Sync(Owner):
    mode: Literal["off", "real_to_gym", "gym_to_real"]


class Scan(StrictModel):
    max_index: int = Field(default=4, ge=0, le=7)


class Assignments(StrictModel):
    back: int | None = Field(default=None, ge=0, le=7)
    front: int | None = Field(default=None, ge=0, le=7)
    wrist: int | None = Field(default=None, ge=0, le=7)

    @model_validator(mode="after")
    def exclusive(self):
        values = [v for v in self.model_dump().values() if v is not None]
        if len(values) != len(set(values)):
            raise ValueError("Each camera may have only one role")
        return self


class ManualOwner(Owner):
    control_epoch: int = Field(ge=0)


class JointTarget(ManualOwner):
    joints: list[float] = Field(min_length=6, max_length=6)


class Torque(ManualOwner):
    enabled: bool


class ToolTarget(ManualOwner):
    # World metres; quaternion is xyzw. Omission preserves measured orientation.
    position: list[float] = Field(min_length=3, max_length=3)
    quaternion: list[float] | None = Field(default=None, min_length=4, max_length=4)
    opening_rad: float | None = Field(default=None, ge=0, le=1.745329252)

    @model_validator(mode="after")
    def rotation(self):
        if self.quaternion is not None:
            norm = math.sqrt(sum(v * v for v in self.quaternion))
            if abs(norm - 1) > 0.001:
                raise ValueError("Quaternion must be normalized (xyzw)")
        return self
