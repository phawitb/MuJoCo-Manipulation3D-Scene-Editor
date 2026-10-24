"""Deterministic, reachable tabletop tasks."""
from .schema import Scene, SceneObject, Task


def example_scene():
    return Scene(name='Pick spoon → cup', objects=[
        SceneObject(id='spoon', name='Pick · spoon', asset='spoon', position=[-.08,-.07,.756], quaternion=[0,0,0,1], mass=.008, color='#e8c97e'),
        SceneObject(id='cup', name='Place · cup', asset='cup', position=[-.04,.09,.802], mass=.10, color='#ef936a'),
    ], task=Task(source='spoon', target='cup'))
