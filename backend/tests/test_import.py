import numpy as np
import pytest
import trimesh
from backend.importer import import_object
from backend.schema import Scene
from backend.simulation import Simulation


@pytest.mark.parametrize('fmt',['stl','obj','glb'])
def test_import_real_mesh_and_portable_roundtrip(fmt):
    raw=trimesh.creation.box().export(file_type=fmt)
    if isinstance(raw,str): raw=raw.encode()
    obj=import_object(raw,f'block.{fmt}',.06)
    assert obj.asset=='mesh'
    assert np.allclose(np.ptp(np.array(obj.mesh.vertices).reshape(-1,3),axis=0),.06)
    scene=Scene(objects=[obj]);s=Simulation(scene)
    assert any(g['kind']=='mesh' and g['owner']==obj.id for g in s.geometry())
    restored=Simulation(Scene.model_validate_json(s.export_scene().model_dump_json()))
    assert restored.snapshot()['meshes']
    restored.step(500)
    assert restored.data.body(f'object_{obj.id}').xpos[2] > .76


def test_import_rejects_bad_file_and_flat_geometry():
    for data,name,size in [(b'bad','bad.stl',.1),(b'no','foo.exe',.1),(b'x'*10_000_001,'a.stl',.1),(b'a','a.obj',float('nan'))]:
        with pytest.raises(ValueError): import_object(data,name,size)
    flat=b'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'
    with pytest.raises(ValueError,match='volume|solid|thickness'): import_object(flat,'flat.obj',.1)
