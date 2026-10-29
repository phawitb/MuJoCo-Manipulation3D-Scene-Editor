"""Bounded, portable settings for local demonstration collection."""

from typing import Annotated, Literal
from pydantic import Field, model_validator
from .appearance import Color, Pattern, Strict

Palette = Annotated[list[Color], Field(max_length=32)]
Patterns = Annotated[list[Pattern], Field(max_length=8)]
Environment = Literal["open", "studio", "room", "warehouse", "panels"]
VIEWS = ("main", "top", "front", "back", "wrist")


class Variation(Strict):
    robot_colors: Palette = Field(default_factory=lambda: ["#f1792e", "#ffd11f"])
    table_colors: Palette = Field(
        default_factory=lambda: ["#ffffff", "#808080", "#202020"]
    )
    motor_colors: Palette = Field(default_factory=list)
    leg_colors: Palette = Field(default_factory=list)
    floor_colors: Palette = Field(default_factory=list)
    wall_colors: Palette = Field(default_factory=list)
    background_colors: Palette = Field(default_factory=list)
    object_colors: Palette = Field(default_factory=list)
    robot_patterns: Patterns = Field(default_factory=list)
    table_patterns: Patterns = Field(default_factory=list)
    floor_patterns: Patterns = Field(default_factory=list)
    wall_patterns: Patterns = Field(default_factory=list)
    environments: list[Environment] = Field(default_factory=list, max_length=5)
    lighting: bool = False
    finishes: bool = False
    repeat_min: float = Field(default=2, ge=1, le=24)
    repeat_max: float = Field(default=12, ge=1, le=24)

    @model_validator(mode="after")
    def ordered(self):
        if self.repeat_min > self.repeat_max:
            raise ValueError("Minimum pattern repeat must not exceed maximum")
        return self


class CollectionConfig(Strict):
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
    max_seconds: int = Field(default=30, ge=1, le=60)
    include_failed: bool = False
    variation: Variation = Field(default_factory=Variation)

    @model_validator(mode="after")
    def seed_range(self):
        if self.seed + self.episodes - 1 > 2**31 - 1:
            raise ValueError("Episode seed range exceeds maximum")
        if not self.task.strip():
            raise ValueError("Task instruction cannot be blank")
        return self
