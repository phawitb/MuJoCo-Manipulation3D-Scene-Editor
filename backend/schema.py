"""Validated, versioned scene contract. SI units; Z up; WXYZ quaternions."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator
import math


def finite_vector(v):
    if not all(math.isfinite(x) and abs(x) <= 100 for x in v):
        raise ValueError('Vector must contain finite values between -100 and 100')
    return v

Vec3 = Annotated[list[float], Field(min_length=3, max_length=3), AfterValidator(finite_vector)]


def quaternion(q):
    if not all(math.isfinite(x) for x in q):
        raise ValueError('Quaternion must be finite')
    norm = math.sqrt(sum(x*x for x in q))
    if norm < 1e-8:
        raise ValueError('Quaternion cannot be zero')
    return [x/norm for x in q]

Quat = Annotated[list[float], Field(min_length=4, max_length=4), AfterValidator(quaternion)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class SceneObject(StrictModel):
    id: str = Field(default='object', pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,63}$')
    name: str = Field(default='Plastic cup', min_length=1, max_length=80)
    asset: Literal['cup', 'plate', 'spoon', 'cube'] = 'cup'
    position: Vec3 = Field(default_factory=lambda: [0, 0.08, 0.802])
    quaternion: Quat = Field(default_factory=lambda: [1, 0, 0, 0])
    scale: float = Field(default=1, ge=0.25, le=3)
    mass: float = Field(default=0.025, ge=0.001, le=10)
    friction: Vec3 = Field(default_factory=lambda: [0.7, 0.005, 0.0001])
    collision: bool = True
    color: str = Field(default='#ef936a', pattern=r'^#[0-9a-fA-F]{6}$')

    @model_validator(mode='after')
    def validate_object(self):
        if any(x < 0 or x > 5 for x in self.friction):
            raise ValueError('Friction must be between 0 and 5')
        if self.id in ('robot', 'table', 'floor'):
            raise ValueError('Reserved object ID')
        if any(abs(x) > 5 for x in self.position):
            raise ValueError('Object must be within 5 m of origin')
        return self


class Table(StrictModel):
    width: float = Field(default=0.8, ge=0.4, le=2)
    depth: float = Field(default=0.6, ge=0.4, le=2)
    height: float = Field(default=0.75, ge=0.4, le=1.2)


class Robot(StrictModel):
    model: Literal['so101'] = 'so101'
    position: Vec3 = Field(default_factory=lambda: [-0.30, 0, 0.754])
    quaternion: Quat = Field(default_factory=lambda: [1, 0, 0, 0])
    joints: list[float] = Field(default_factory=lambda: [0, -0.7, 0.7, 0.3, 0, 0.6], min_length=6, max_length=6)


class Scene(StrictModel):
    version: Literal[1] = 1
    name: str = Field(default='Untitled workspace', max_length=100)
    table: Table = Field(default_factory=Table)
    robot: Robot = Field(default_factory=Robot)
    objects: list[SceneObject] = Field(default_factory=list, max_length=64)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({obj.id for obj in self.objects}) != len(self.objects):
            raise ValueError('Object IDs must be unique')
        return self


ASSETS = [
    dict(id='cup', name='Plastic cup', category='Cups', dimensions=[.072, .072, .10], mass=.025, color='#ef936a', description='Open cup · compound walls'),
    dict(id='plate', name='Plastic plate', category='Plates', dimensions=[.14, .14, .012], mass=.04, color='#8fb9b1', description='Shallow plate · raised rim'),
    dict(id='spoon', name='Plastic spoon', category='Spoons', dimensions=[.15, .032, .008], mass=.008, color='#e8c97e', description='Rounded bowl + handle'),
    dict(id='cube', name='Test cube', category='Other Objects', dimensions=[.04, .04, .04], mass=.05, color='#a7a6dc', description='Calibration block · 40 mm'),
]
