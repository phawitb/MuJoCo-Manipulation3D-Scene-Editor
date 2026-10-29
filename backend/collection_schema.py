"""Bounded, portable settings for local demonstration collection."""

from typing import Annotated, Literal
from pydantic import Field, model_validator
from .appearance import Color, Pattern, Strict

Palette = Annotated[list[Color], Field(max_length=32)]
Patterns = Annotated[list[Pattern], Field(max_length=8)]
Environment = Literal["open", "studio", "room", "warehouse", "panels"]
ALL_COLORS = [
    "#f1792e",
    "#ffd11f",
    "#ffffff",
    "#808080",
    "#202020",
    "#668ad5",
    "#6f9b77",
    "#e78dbe",
    "#d95454",
]
ALL_PATTERNS = [
    "solid",
    "checker",
    "stripes",
    "dots",
    "wood",
    "terrazzo",
    "tiles",
    "noise",
]
ALL_ENVIRONMENTS = ["open", "studio", "room", "warehouse", "panels"]
VIEWS = ("main", "top", "front", "back", "wrist")


class Variation(Strict):
    robot_colors: Palette = Field(default_factory=lambda: ["#f1792e", "#ffd11f"])
    table_colors: Palette = Field(default_factory=lambda: ALL_COLORS.copy())
    motor_colors: Palette = Field(default_factory=lambda: ALL_COLORS.copy())
    leg_colors: Palette = Field(default_factory=lambda: ALL_COLORS.copy())
    floor_colors: Palette = Field(default_factory=lambda: ALL_COLORS.copy())
    wall_colors: Palette = Field(default_factory=lambda: ALL_COLORS.copy())
    background_colors: Palette = Field(default_factory=lambda: ALL_COLORS.copy())
    object_colors: Palette = Field(default_factory=lambda: ALL_COLORS.copy())
    robot_patterns: Patterns = Field(default_factory=lambda: ALL_PATTERNS.copy())
    table_patterns: Patterns = Field(default_factory=lambda: ALL_PATTERNS.copy())
    floor_patterns: Patterns = Field(default_factory=lambda: ALL_PATTERNS.copy())
    wall_patterns: Patterns = Field(default_factory=lambda: ALL_PATTERNS.copy())
    environments: list[Environment] = Field(
        default_factory=lambda: ALL_ENVIRONMENTS.copy(), max_length=5
    )
    lighting: bool = True
    finishes: bool = True
    positions: bool = True
    position_mode: Literal["radius", "workspace"] = "workspace"
    position_radius: float = Field(default=0.02, ge=0.01, le=0.40)
    repeat_min: float = Field(default=2, ge=1, le=24)
    repeat_max: float = Field(default=12, ge=1, le=24)

    @model_validator(mode="before")
    @classmethod
    def legacy_positions(cls, values):
        if (
            isinstance(values, dict)
            and "position_radius" in values
            and "position_mode" not in values
        ):
            return {**values, "position_mode": "radius"}
        return values

    @model_validator(mode="after")
    def ordered(self):
        if self.repeat_min > self.repeat_max:
            raise ValueError("Minimum pattern repeat must not exceed maximum")
        return self


class CollectionConfig(Strict):
    top_reference_height: float = Field(default=480, ge=1, le=16384)
    cameras: list[Literal["main", "top", "front", "back", "wrist"]] = Field(
        default_factory=lambda: list(VIEWS), min_length=1, max_length=5
    )
    scene_id: str | None = Field(default=None, max_length=80)
    name: str = Field(
        default="so101-demonstrations", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$"
    )
    task: str = Field(
        default="Pick up the source object and place it in the destination.",
        min_length=1,
        max_length=500,
    )
    episodes: int = Field(default=5, ge=1, le=100)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    fps: Literal[10, 20, 25, 50] = 20
    resolution: Literal["640x480", "320x240"] = "640x480"
    duration_mode: Literal["auto", "fixed"] = "auto"
    max_seconds: int = Field(default=30, ge=1, le=120)
    include_failed: bool = False
    variation: Variation = Field(default_factory=Variation)

    @model_validator(mode="before")
    @classmethod
    def legacy_duration(cls, values):
        if (
            isinstance(values, dict)
            and "max_seconds" in values
            and "duration_mode" not in values
        ):
            return {**values, "duration_mode": "fixed"}
        return values

    @model_validator(mode="after")
    def seed_range(self):
        if len(set(self.cameras)) != len(self.cameras):
            raise ValueError("Select each camera only once")
        if self.scene_id is not None:
            from .examples import example_catalog

            if self.scene_id not in {s["id"] for s in example_catalog()}:
                raise ValueError("Unknown collection scene")
        if self.seed + self.max_attempts - 1 > 2**31 - 1:
            raise ValueError("Episode seed range exceeds maximum")
        if not self.task.strip():
            raise ValueError("Task instruction cannot be blank")
        return self

    @property
    def max_attempts(self):
        return self.episodes * (
            50
            if self.variation.positions and self.variation.position_mode == "workspace"
            else 5
        )
