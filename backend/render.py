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
    with CameraRenderer(sim) as renderer:
        result = io.BytesIO()
        Image.fromarray(renderer.capture(payload["view"])).save(result, format="PNG")
        return result.getvalue()


def camera_for_view(sim, view, top_reference_height=480):
    # Match the editor's clipping and reset free-camera projection between views.
    sim.model.vis.map.znear = 0.005 / sim.model.stat.extent
    sim.model.vis.map.zfar = 20 / sim.model.stat.extent
    sim.model.vis.global_.orthographic = int(view == "top")
    camera = "wrist_cam"
    if view != "wrist":
        config = sim.scene.cameras[view]
        delta = np.array(config.position) - config.target
        camera = mujoco.MjvCamera()
        camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        camera.lookat[:] = config.target
        camera.distance = float(np.linalg.norm(delta))
        # MuJoCo azimuth describes the viewing direction, opposite the eye offset.
        camera.azimuth = math.degrees(math.atan2(delta[1], delta[0])) + 180
        camera.elevation = -math.degrees(math.asin(delta[2] / np.linalg.norm(delta)))
        sim.model.vis.global_.fovy = math.degrees(
            2 * math.atan(math.tan(math.radians(config.fov / 2)) / config.zoom)
        )
        if view == "top":
            camera.orthographic = 1
            camera.azimuth = 0
            # Orthographic fovy is a world-space height, not an angle. Three's
            # Top frustum is measured in CSS pixels before division by zoom.
            sim.model.vis.global_.fovy = top_reference_height / config.zoom
    return camera


class CameraRenderer:
    """Persistent native renderer; all captures read the same physical state."""

    def __init__(self, sim, width=640, height=480, top_reference_height=480):
        self.sim = sim
        self.top_reference_height = top_reference_height
        self.renderer = mujoco.Renderer(sim.model, height=height, width=width)
        self.option = mujoco.MjvOption()
        self.option.geomgroup[3:] = 0
        self.option.sitegroup[:] = 0

    def capture(self, view):
        self.renderer.update_scene(
            self.sim.data,
            camera=camera_for_view(self.sim, view, self.top_reference_height),
            scene_option=self.option,
        )
        return self.renderer.render().copy()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.renderer.close()


if __name__ == "__main__":
    sys.stdout.buffer.write(render(json.load(sys.stdin)))
