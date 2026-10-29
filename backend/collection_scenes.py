"""Select a dataset's physical scene without changing the live editor."""

from .examples import example_catalog, example_scene


def collection_scene(current, scene_id):
    if scene_id is None:
        return current.model_copy(deep=True)
    selected = example_scene(scene_id)
    selected.appearance = current.appearance.model_copy(deep=True)
    selected.cameras = {
        key: value.model_copy(deep=True) for key, value in current.cameras.items()
    }
    selected.table.color = current.table.color
    return selected


def collection_catalog():
    scenes = example_catalog()
    for row in scenes:
        scene = example_scene(row["id"])
        objects = {o.id: o for o in scene.objects}
        source = objects[scene.task.source].name.split("·")[-1].strip()
        target = objects[scene.task.target].name.split("·")[-1].strip()
        row["instruction"] = f"Pick up {source} and place it in or on {target}."
    return scenes
