"""Real geometry tests: protect holes, units, solid output and bounded input."""
import base64
import io
import importlib
import numpy as np
import pytest
import trimesh
from PIL import Image, ImageDraw


def api():
    try:
        return importlib.import_module('backend.modules.blender.service')
    except ModuleNotFoundError:
        pytest.fail('Local reconstruction service has not been implemented')


def picture(hole=False, rgba=False):
    image = Image.new('RGBA' if rgba else 'RGB', (80, 100), (255, 255, 255, 0) if rgba else 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 69, 89), fill=(0, 0, 0, 255) if rgba else 'black')
    if hole:
        draw.rectangle((25, 30, 54, 69), fill=(255, 255, 255, 0) if rgba else 'white')
    data = io.BytesIO()
    image.save(data, format='PNG')
    return data.getvalue()


def request(data=None, **kwargs):
    schemas = importlib.import_module('backend.modules.blender.schemas')
    return schemas.ReconstructionRequest(image_base64=base64.b64encode(data or picture()).decode(), filename='sample.png', width_m=.12, height_m=.16, depth_m=.03, **kwargs)


def mesh_of(result):
    return trimesh.Trimesh(np.array(result.object.mesh.vertices).reshape(-1, 3), np.array(result.object.mesh.faces).reshape(-1, 3), process=False)


def test_extrusion_preserves_hole_and_metric_dimensions():
    service = api()
    result = service.reconstruct(request(picture(hole=True)))
    mesh = mesh_of(result)
    assert mesh.is_watertight and mesh.is_volume
    assert np.allclose(mesh.extents, [.12, .03, .16])
    assert mesh.euler_number == 0  # One actual through-hole, not a filled convex hull.
    assert .00035 < mesh.volume < .0005
    assert len(mesh.vertices) <= 20000 and len(mesh.faces) <= 40000
    glb = trimesh.load(io.BytesIO(base64.b64decode(result.glb_base64)), file_type='glb', force='mesh')
    assert glb.is_volume
    # glTF is Y-up; Gym portable geometry is Z-up. Blender converts on import.
    assert np.allclose(glb.extents, [.12, .16, .03])


def test_revolve_is_closed_solid_with_exact_diameter_and_height():
    result = api().reconstruct(request(mode='revolve'))
    mesh = mesh_of(result)
    assert mesh.is_volume and mesh.is_watertight
    assert np.allclose(mesh.extents, [.12, .12, .16])
    assert mesh.volume == pytest.approx(np.pi * .06 ** 2 * .16, rel=.01)


def test_transparency_can_define_silhouette():
    result = api().reconstruct(request(picture(hole=True, rgba=True), foreground='alpha'))
    assert mesh_of(result).is_volume and mesh_of(result).euler_number == 0


def test_blank_and_malformed_images_rejected():
    service = api()
    blank = io.BytesIO()
    Image.new('RGB', (40, 40), 'white').save(blank, format='PNG')
    for data in [blank.getvalue(), b'not an image']:
        with pytest.raises(ValueError, match='foreground|image|PNG|JPEG'):
            service.reconstruct(request(data))


def test_pixel_and_encoded_input_budgets():
    service = api()
    huge = io.BytesIO()
    Image.new('1', (5000, 4000)).save(huge, format='PNG')
    with pytest.raises(ValueError, match='pixels|dimensions'):
        service.reconstruct(request(huge.getvalue()))
    with pytest.raises(ValueError):
        service.reconstruct(request(b'x' * 6_000_001))


def test_invalid_dimensions_and_unknown_options_rejected():
    api()
    from backend.modules.blender.schemas import ReconstructionRequest
    for extra in [{'width_m': float('nan')}, {'depth_m': 0}, {'remote_upload': True}, {'threshold': 300}, {'mode': 'ai'}]:
        with pytest.raises(ValueError):
            ReconstructionRequest(image_base64='AAAA', **extra)


def test_generated_object_roundtrips_through_gym_command():
    from backend.sessions import Command, Session
    from backend.schema import Scene
    obj = api().reconstruct(request()).object
    session = Session()
    session.execute(Command(type='object_add', object=obj.model_dump()))
    scene = Scene.model_validate_json(session.sim.export_scene().model_dump_json())
    assert any(o.id == obj.id and o.mesh for o in scene.objects)
    assert session.packet()['meshes']


def test_light_foreground_and_discarded_speck_are_reported():
    image = Image.new('RGB', (80, 100), 'black')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 69, 89), fill='white')
    draw.rectangle((1, 1, 3, 3), fill='white')
    data = io.BytesIO()
    image.save(data, format='PNG')
    result = api().reconstruct(request(data.getvalue(), foreground='light'))
    assert mesh_of(result).is_volume
    assert any('Detached' in w for w in result.metadata.warnings)


def test_bad_base64_and_opaque_alpha_selection_rejected():
    service = api()
    from backend.modules.blender.schemas import ReconstructionRequest
    with pytest.raises(ValueError, match='base64'):
        service.reconstruct(ReconstructionRequest(image_base64='bad!'))
    with pytest.raises(ValueError, match='foreground'):
        service.reconstruct(request(foreground='alpha'))
