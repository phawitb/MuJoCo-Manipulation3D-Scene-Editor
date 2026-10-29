import math
import mujoco
import numpy as np
import pytest
from backend.simulation import Simulation
from backend.render import camera_for_view


def native_camera(sim, view, **kwargs):
    camera = camera_for_view(sim, view, **kwargs)
    if isinstance(camera, str):
        name = camera
        camera = mujoco.MjvCamera()
        camera.type = mujoco.mjtCamera.mjCAMERA_FIXED
        camera.fixedcamid = sim.model.camera(name).id
    scene = mujoco.MjvScene(sim.model, maxgeom=10000)
    mujoco.mjv_updateScene(
        sim.model,
        sim.data,
        mujoco.MjvOption(),
        None,
        camera,
        mujoco.mjtCatBit.mjCAT_ALL,
        scene,
    )
    return mujoco.mjv_averageCamera(scene.camera[0], scene.camera[1])


@pytest.mark.parametrize("view", ["main", "front", "back"])
@pytest.mark.parametrize("zoom", [0.7, 1, 2.5])
def test_native_perspective_matches_editor_pose_and_projection(view, zoom):
    sim = Simulation()
    config = sim.scene.cameras[view]
    config.zoom = zoom
    config.target = [0.06, -0.03, 0.79]
    actual = native_camera(sim, view)
    np.testing.assert_allclose(actual.pos, config.position, atol=1e-6)
    forward = np.array(config.target) - config.position
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0, 0, 1])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    np.testing.assert_allclose(actual.forward, forward, atol=1e-6)
    np.testing.assert_allclose(actual.up, up, atol=1e-6)
    assert actual.frustum_near == pytest.approx(0.005, rel=1e-6)
    assert actual.frustum_far == pytest.approx(20, rel=1e-6)
    assert not actual.orthographic
    assert actual.frustum_top / actual.frustum_near == pytest.approx(
        math.tan(math.radians(config.fov / 2)) / zoom, rel=1e-6
    )


@pytest.mark.parametrize("reference_height", [300, 480, 850])
def test_top_is_true_orthographic_and_matches_editor_visible_height(reference_height):
    sim = Simulation()
    config = sim.scene.cameras["top"]
    config.zoom = 507.735
    actual = native_camera(sim, "top", top_reference_height=reference_height)
    assert actual.orthographic
    np.testing.assert_allclose(actual.pos, config.position, atol=1e-6)
    np.testing.assert_allclose(actual.forward, [0, 0, -1], atol=1e-6)
    np.testing.assert_allclose(actual.up, [1, 0, 0], atol=1e-6)
    assert actual.frustum_top - actual.frustum_bottom == pytest.approx(
        reference_height / config.zoom, rel=1e-6
    )


def test_top_does_not_leak_projection_into_wrist_or_main():
    sim = Simulation()
    native_camera(sim, "top")
    wrist = native_camera(sim, "wrist")
    assert not wrist.orthographic
    assert wrist.frustum_top / wrist.frustum_near == pytest.approx(
        math.tan(math.radians(61 / 2)), rel=1e-6
    )
    expected = sim.data.camera("wrist_cam")
    np.testing.assert_allclose(wrist.pos, expected.xpos, atol=1e-6)
    np.testing.assert_allclose(
        wrist.forward, -expected.xmat.reshape(3, 3)[:, 2], atol=1e-6
    )
    main = native_camera(sim, "main")
    assert not main.orthographic
    np.testing.assert_allclose(main.pos, sim.scene.cameras["main"].position, atol=1e-6)
