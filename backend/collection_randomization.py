"""Independent property streams: adding a scope cannot perturb another scope."""

import random
from .appearance import Randomization, randomize_scene
from .collection_schema import Variation
from .schema import Scene


def episode_scene(source: Scene, config: Variation, seed: int) -> Scene:
    scene = source.model_copy(deep=True)
    a = scene.appearance

    def stream(key):
        return random.Random(f"collection-v1:{seed}:{key}")

    for key in ("robot", "motor", "leg", "floor", "wall", "background"):
        choices = getattr(config, key + "_colors")
        if choices:
            setattr(
                a,
                "background" if key == "background" else key + "_color",
                stream(key).choice(choices),
            )
    if config.table_colors:
        scene.table.color = stream("table").choice(config.table_colors)
    for obj in scene.objects:
        if config.object_colors:
            obj.color = stream("object:" + obj.id).choice(config.object_colors)
    for key in ("robot", "table", "floor", "wall"):
        patterns = getattr(config, key + "_patterns")
        surface = getattr(a, key)
        if patterns:
            rng = stream(key + "_pattern")
            surface.pattern = rng.choice(patterns)
            surface.repeat = round(rng.uniform(config.repeat_min, config.repeat_max), 2)
        colors = getattr(config, key + "_colors")
        if colors:
            surface.secondary = stream(key + "_secondary").choice(colors)
        if config.finishes:
            rng = stream(key + "_finish")
            surface.roughness = round(rng.uniform(0.2, 1), 2)
            surface.metallic = round(rng.uniform(0, 0.6), 2)
    if config.environments:
        a.environment = stream("environment").choice(config.environments)
    if config.lighting:
        scene = randomize_scene(scene, Randomization(seed=seed, groups=["lighting"]))
    scene.appearance.last_randomization = None
    return Scene.model_validate(scene.model_dump())
