import numpy as np
import pytest
from pydantic import ValidationError
from backend.schema import Scene, SceneObject
from backend.simulation import Simulation


def test_default_scene_is_empty_fixed_and_collision_free():
    sim = Simulation()
    assert sim.scene.objects == []
    assert sim.model.nq == 6
    assert sim.data.time == 0
    assert not sim.running
    assert not any(c.dist < -1e-5 for c in sim.data.contact)
    base = sim.data.xpos[sim.model.body('base').id].copy()
    sim.step(500)
    np.testing.assert_allclose(sim.data.xpos[sim.model.body('base').id], base)


@pytest.mark.parametrize('asset', ['cup', 'plate', 'spoon'])
def test_objects_fall_and_settle_on_table(asset):
    sim = Simulation(Scene(objects=[SceneObject(id='drop', asset=asset, position=[0, 0.08, 1.0])]))
    start = sim.state()['objects'][0]['position'][2]
    sim.step(1500)
    obj = sim.state()['objects'][0]
    assert 0.72 < obj['position'][2] < 0.9
    assert obj['position'][2] < start
    assert np.isfinite(sim.data.qpos).all()
    assert np.linalg.norm(sim.data.qvel[-6:]) < 0.02


def test_schema_rejects_invalid_scene():
    with pytest.raises(ValidationError):
        Scene(objects=[SceneObject(id='x'), SceneObject(id='x')])
    with pytest.raises(ValidationError):
        SceneObject(position=[float('nan'), 0, 1])
    with pytest.raises(ValidationError):
        SceneObject(mass=-1)
    with pytest.raises(ValidationError):
        SceneObject(scale=0)


def test_geometry_and_state_ids_match_and_meshes_exist():
    sim = Simulation(Scene(objects=[SceneObject(id='cup1')]))
    packet = sim.snapshot()
    assert packet['type'] == 'snapshot'
    assert len(packet['geometry']) == len(packet['poses'])
    assert any(g['owner'] == 'cup1' for g in packet['geometry'])
    assert any(g['kind'] == 'mesh' for g in packet['geometry'])
    for geom in packet['geometry']:
        if geom['kind'] == 'mesh':
            mesh = sim.meshes()[str(geom['mesh'])]
            assert len(mesh['vertices']) > 0
            assert max(mesh['faces']) < len(mesh['vertices']) / 3


def test_edit_after_physics_preserves_live_pose():
    sim = Simulation(Scene(objects=[SceneObject(id='cup1', position=[0, .1, 1.1])]))
    sim.step(100)
    live = sim.export_scene()
    assert live.objects[0].position[2] != 1.1
    sim.load(live)
    np.testing.assert_allclose(sim.state()['objects'][0]['position'], live.objects[0].position)


def test_sessions_do_not_share_state():
    a, b = Simulation(), Simulation()
    a.load(Scene(objects=[SceneObject(id='one')]))
    a.step(5)
    assert not b.scene.objects and b.data.time == 0


def test_robot_joint_limits_rejected():
    sim = Simulation()
    original = sim.scene.model_dump()
    bad = sim.scene.model_copy(deep=True)
    bad.robot.joints = [100] * 6
    with pytest.raises(ValueError):
        sim.load(bad)
    assert sim.scene.model_dump() == original
