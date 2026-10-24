"""Validated, versioned scene contract. SI units; Z up; WXYZ quaternions."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator
import math
import json
from .catalog import KALAS_ASSETS

MAX_SCENE_BYTES = 8_000_000


def finite_vector(v):
    if not all(math.isfinite(x) and abs(x) <= 100 for x in v):
        raise ValueError("Vector must contain finite values between -100 and 100")
    return v


Vec3 = Annotated[
    list[float], Field(min_length=3, max_length=3), AfterValidator(finite_vector)
]


def quaternion(q):
    if not all(math.isfinite(x) for x in q):
        raise ValueError("Quaternion must be finite")
    norm = math.sqrt(sum(x * x for x in q))
    if norm < 1e-8:
        raise ValueError("Quaternion cannot be zero")
    return [x / norm for x in q]


Quat = Annotated[
    list[float], Field(min_length=4, max_length=4), AfterValidator(quaternion)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ImportedMesh(StrictModel):
    vertices: list[float] = Field(min_length=12, max_length=60000)
    faces: list[int] = Field(min_length=12, max_length=120000)
    filename: str = Field(max_length=120)

    @model_validator(mode="after")
    def geometry(self):
        if len(self.vertices) % 3 or len(self.faces) % 3:
            raise ValueError("Mesh arrays must contain triples")
        if any(not math.isfinite(x) or abs(x) > 2 for x in self.vertices):
            raise ValueError("Mesh vertices must be finite and within 2 m")
        if any(i < 0 or i >= len(self.vertices) // 3 for i in self.faces):
            raise ValueError("Mesh face references missing vertex")
        return self


class SceneObject(StrictModel):
    id: str = Field(default="object", pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    name: str = Field(default="Plastic cup", min_length=1, max_length=80)
    asset: Literal[
        "cup",
        "plate",
        "spoon",
        "cube",
        "mesh",
        "kalas_bowl",
        "kalas_cup",
        "kalas_spoon",
        "kalas_plate",
    ] = "cup"
    mesh: ImportedMesh | None = None
    position: Vec3 = Field(default_factory=lambda: [0, 0.08, 0.802])
    quaternion: Quat = Field(default_factory=lambda: [1, 0, 0, 0])
    scale: float = Field(default=1, ge=0.25, le=3)
    mass: float = Field(default=0.025, ge=0.001, le=10)
    friction: Vec3 = Field(default_factory=lambda: [0.7, 0.005, 0.0001])
    collision: bool = True
    color: str = Field(default="#ef936a", pattern=r"^#[0-9a-fA-F]{6}$")

    @model_validator(mode="after")
    def validate_object(self):
        if (self.asset == "mesh") != (self.mesh is not None):
            raise ValueError(
                "Imported objects require mesh data; primitives cannot contain it"
            )
        if any(x < 0 or x > 5 for x in self.friction):
            raise ValueError("Friction must be between 0 and 5")
        if self.id in ("robot", "table", "floor"):
            raise ValueError("Reserved object ID")
        if any(abs(x) > 5 for x in self.position):
            raise ValueError("Object must be within 5 m of origin")
        return self


class Table(StrictModel):
    width: float = Field(default=0.8, ge=0.4, le=2)
    depth: float = Field(default=0.6, ge=0.4, le=2)
    height: float = Field(default=0.75, ge=0.4, le=1.2)


class Robot(StrictModel):
    model: Literal["so101"] = "so101"
    position: Vec3 = Field(default_factory=lambda: [-0.30, 0, 0.754])
    quaternion: Quat = Field(default_factory=lambda: [1, 0, 0, 0])
    joints: list[float] = Field(
        default_factory=lambda: [0, -0.7, 0.7, 0.3, 0, 0.6], min_length=6, max_length=6
    )


class Camera(StrictModel):
    position: Vec3
    target: Vec3
    zoom: float = Field(default=1, gt=0, le=10000)
    fov: float = Field(default=50, ge=15, le=100)

    @model_validator(mode="after")
    def distinct(self):
        if math.dist(self.position, self.target) < 0.01:
            raise ValueError("Camera must be away from its target")
        return self


class Task(StrictModel):
    source: str | None = None
    target: str | None = None


def default_cameras():
    return {
        "main": Camera(position=[1.05, -1.25, 1.55], target=[0, 0, 0.77], fov=42),
        "top": Camera(position=[0, 0, 2.6], target=[0, 0, 0.75], zoom=320),
        "back": Camera(position=[-0.30, 0, 1.65], target=[0, 0, 0.80], fov=55),
        "front": Camera(position=[0.65, -0.75, 1.3], target=[-0.04, 0, 0.82], fov=50),
    }


class Scene(StrictModel):
    version: Literal[1] = 1
    name: str = Field(default="Untitled workspace", max_length=100)
    table: Table = Field(default_factory=Table)
    robot: Robot = Field(default_factory=Robot)
    task: Task = Field(default_factory=Task)
    cameras: dict[Literal["main", "top", "front", "back"], Camera] = Field(
        default_factory=default_cameras
    )
    objects: list[SceneObject] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({obj.id for obj in self.objects}) != len(self.objects):
            raise ValueError("Object IDs must be unique")
        ids = {o.id for o in self.objects}
        if self.task.source is not None and self.task.source not in ids:
            raise ValueError("Task source no longer exists")
        if self.task.target is not None and self.task.target not in ids:
            raise ValueError("Task target no longer exists")
        if self.task.source and self.task.source == self.task.target:
            raise ValueError("Pick and place objects must be different")
        self.cameras = {**default_cameras(), **self.cameras}
        top = self.cameras["top"]
        if (
            abs(top.position[0] - top.target[0]) > 1e-5
            or abs(top.position[1] - top.target[1]) > 1e-5
            or top.position[2] <= top.target[2]
        ):
            raise ValueError("Top camera must look vertically down")
        # Budget the actual formatted portable document, not each individual edit.
        # Reserve pose/command/camera overhead and JS's longer decimal spelling of
        # small floats (at most three extra bytes per mesh coordinate).
        data = self.model_dump()
        # Physics changes these values without editing. Budget their worst-case
        # numeric width so a near-limit scene remains loadable after it moves.
        number_slot = "-0.123456789012345678901234567890"
        for obj in data["objects"]:
            obj["position"] = [number_slot] * 3
            obj["quaternion"] = [number_slot] * 4
        data["robot"]["joints"] = [number_slot] * 6
        document = {"version": 1, "scene": data, "cameras": data["cameras"]}
        size = len(json.dumps(document, indent=2, ensure_ascii=True).encode())
        size += 64_000 + 3 * sum(len(o.mesh.vertices) for o in self.objects if o.mesh)
        if size > MAX_SCENE_BYTES:
            raise ValueError(
                "Scene exceeds the portable 8 MB size budget. Remove an object or simplify its mesh."
            )
        return self


ASSETS = KALAS_ASSETS + [
    dict(
        id="cup",
        name="Plastic cup",
        category="Cups",
        dimensions=[0.072, 0.072, 0.10],
        mass=0.025,
        color="#ef936a",
        description="Open cup · compound walls",
    ),
    dict(
        id="plate",
        name="Plastic plate",
        category="Plates",
        dimensions=[0.14, 0.14, 0.012],
        mass=0.04,
        color="#8fb9b1",
        description="Shallow plate · raised rim",
    ),
    dict(
        id="spoon",
        name="Plastic spoon",
        category="Spoons",
        dimensions=[0.15, 0.032, 0.008],
        mass=0.008,
        color="#e8c97e",
        description="Rounded bowl + handle",
    ),
    dict(
        id="cube",
        name="Test cube",
        category="Other Objects",
        dimensions=[0.04, 0.04, 0.04],
        mass=0.05,
        color="#a7a6dc",
        description="Calibration block · 40 mm",
    ),
]
