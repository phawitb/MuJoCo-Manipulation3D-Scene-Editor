"""One-shot native MuJoCo camera observation, isolated for macOS GL context safety."""

import io
import json
import math
import sys
import numpy as np
import mujoco
from PIL import Image
from .schema import Scene
from .simulation import Simulation


def render(payload):
    sim = Simulation(Scene.model_validate(payload["scene"]))
    sim.data.qpos[:6] = payload["joints"]
    mujoco.mj_forward(sim.model, sim.data)
    view = payload["view"]
    camera = "wrist_cam"
    if view != "wrist":
        config = sim.scene.cameras[view]
        delta = np.array(config.position) - config.target
        camera = mujoco.MjvCamera()
        camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        camera.lookat[:] = config.target
        camera.distance = (
            float(np.linalg.norm(delta)) / config.zoom if view != "top" else 1.5
        )
        camera.azimuth = math.degrees(math.atan2(delta[1], delta[0]))
        camera.elevation = -math.degrees(math.asin(delta[2] / np.linalg.norm(delta)))
        sim.model.vis.global_.fovy = config.fov
        if view == "top":
            camera.orthographic = 1
            camera.azimuth = 0
            camera.distance = 480 / (
                config.zoom * 2 * math.tan(math.radians(config.fov / 2))
            )
    with mujoco.Renderer(sim.model, height=480, width=640) as renderer:
        option = mujoco.MjvOption()
        option.geomgroup[3:] = 0
        option.sitegroup[:] = 0
        renderer.update_scene(sim.data, camera=camera, scene_option=option)
        result = io.BytesIO()
        Image.fromarray(renderer.render()).save(result, format="PNG")
        return result.getvalue()


if __name__ == "__main__":
    sys.stdout.buffer.write(render(json.load(sys.stdin)))
