"""Package boundary regressions: source physics, portable geometry and rejection."""

import io
import zipfile
import numpy as np
import pytest
import trimesh


def fixture_files():
    return {
        "scene.xml": b'<mujoco><compiler angle="radian"/><include file="assets.xml"/><worldbody><geom type="plane" size="1 1 .1"/><frame pos="0 0 .12"><include file="object.xml"/></frame></worldbody></mujoco>',
        "assets.xml": b'<mujocoinclude><asset><mesh name="case" file="meshes/case.obj"/></asset></mujocoinclude>',
        "object.xml": b"""<mujocoinclude><body name="sensor"><freejoint/>
          <inertial mass=".045" pos=".002 .003 .004" fullinertia=".000018 .000015 .000017 0 0 -.000005"/>
          <geom type="mesh" mesh="case" pos=".01 0 .01" rgba=".1 .2 .3 1" group="2" contype="0" conaffinity="0" mass="0"/>
          <geom type="box" size=".025 .015 .005" pos=".01 0 .01" group="3" mass="0" friction=".6 .004 .0002" condim="4" priority="1" solref=".004 1" solimp=".95 .99 .001"/>
          <site name="grasp" pos=".01 0 .01" size=".001"/>
        </body></mujocoinclude>""",
        "meshes/case.obj": trimesh.creation.box(extents=[0.05, 0.03, 0.01])
        .export(file_type="obj")
        .encode(),
        "physics.json": b'{"mass_source":"estimated"}',
    }


def read_package(files=None):
    from backend.package_importer import import_package

    return import_package(fixture_files() if files is None else files)


def test_package_preserves_source_dimensions_mass_and_parts():
    obj = read_package()
    assert obj.asset == "mujoco"
    assert obj.name == "sensor"
    assert obj.mass == pytest.approx(0.045)
    assert obj.package.dimensions == pytest.approx([0.05, 0.03, 0.01])
    assert len(obj.package.geoms) == 2
    assert obj.package.geoms[0].rgba == pytest.approx([0.1, 0.2, 0.3, 1])
    assert obj.package.geoms[1].friction == pytest.approx([0.6, 0.004, 0.0002])
    assert obj.package.com == pytest.approx([-0.008, 0.003, -0.006])
    assert obj.package.provenance["physics.json"]["mass_source"] == "estimated"


def test_nested_zip_and_folder_are_equivalent():
    from backend.package_importer import import_package_zip

    folder = {"my object/" + p: b for p, b in fixture_files().items()}
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as archive:
        for p, b in folder.items():
            archive.writestr(p, b)
    a, b = read_package(folder), import_package_zip(z.getvalue())
    assert a.package == b.package


@pytest.mark.parametrize(
    "path", ["../outside.obj", "/tmp/out.obj", "meshes/../../bad", "C:/bad.obj", "a\\b"]
)
def test_package_rejects_unsafe_paths(path):
    files = fixture_files()
    files[path] = b"bad"
    with pytest.raises(ValueError, match="path|Path"):
        read_package(files)


@pytest.mark.parametrize(
    "change,message",
    [
        ("joint", "joint|articulat"),
        ("missing", "missing|Missing"),
        ("entity", "entit|DOCTYPE"),
        ("plugin", "Unsupported|unsupported"),
        ("inertia", "inertia|Inertia|inertial"),
    ],
)
def test_rejects_unsupported_or_invalid_package(change, message):
    files = fixture_files()
    if change == "joint":
        files["object.xml"] = files["object.xml"].replace(
            b"<freejoint/>", b'<joint type="hinge"/>'
        )
    if change == "missing":
        del files["meshes/case.obj"]
    if change == "entity":
        files["object.xml"] = (
            b'<!DOCTYPE x [<!ENTITY y SYSTEM "file:///etc/passwd">]>'
            + files["object.xml"]
        )
    if change == "plugin":
        files["object.xml"] = files["object.xml"].replace(
            b"<freejoint/>", b'<plugin plugin="bad"/>'
        )
    if change == "inertia":
        files["object.xml"] = files["object.xml"].replace(
            b".000018 .000015 .000017", b"-.000018 .000015 .000017"
        )
    with pytest.raises(ValueError, match=message):
        read_package(files)


def test_compiled_package_roundtrip_and_scaled_inertia():
    from backend.schema import Scene
    from backend.simulation import Simulation
    from backend.catalog import profile

    obj = read_package()
    sim = Simulation(Scene(objects=[obj]))
    bid = sim.model.body("object_" + obj.id).id
    assert sim.model.body_mass[bid] == pytest.approx(0.045)
    assert sim.model.body_ipos[bid] == pytest.approx([-0.008, 0.003, -0.006])
    rot = np.empty(9)
    import mujoco

    mujoco.mju_quat2Mat(rot, sim.model.body_iquat[bid])
    tensor = (
        rot.reshape(3, 3) @ np.diag(sim.model.body_inertia[bid]) @ rot.reshape(3, 3).T
    )
    expected = np.array(
        [[0.000018, 0, 0], [0, 0.000015, -0.000005], [0, -0.000005, 0.000017]]
    )
    assert tensor == pytest.approx(expected)
    assert profile(obj)["dimensions"] == pytest.approx([0.05, 0.03, 0.01])
    # Scaling holds the separate mass setting fixed, so inertia scales as length squared.
    obj.scale = 2
    obj.mass = 0.09
    dup = obj.model_copy(deep=True)
    dup.id = "other"
    dup.position[1] = 0.12
    restored = Simulation(
        Scene.model_validate_json(Scene(objects=[obj, dup]).model_dump_json())
    )
    assert restored.model.body("object_" + obj.id).mass == pytest.approx([0.09])
    assert restored.model.body("object_" + obj.id).inertia == pytest.approx(
        sim.model.body_inertia[bid] * 8
    )
    restored.step(1000)
    assert np.isfinite(restored.data.qpos).all()
    assert restored.data.body("object_" + obj.id).xpos[2] > 0.75


def test_color_and_friction_overrides_and_reset():
    from backend.sessions import Session, Command

    obj = read_package()
    session = Session()
    session.execute(Command(type="object_add", object=obj.model_dump()))

    def geom():
        return session.sim.model.geom("obj_" + obj.id + "_0")

    assert geom().rgba == pytest.approx([0.1, 0.2, 0.3, 1])
    session.execute(
        Command(
            type="object_update",
            id=obj.id,
            patch={"color": "#ff0000", "friction": [0.9, 0.01, 0.001]},
        )
    )
    assert geom().rgba == pytest.approx([1, 0, 0, 1])
    assert session.sim.model.geom("obj_" + obj.id + "_1").friction == pytest.approx(
        [0.9, 0.01, 0.001]
    )
    session.execute(
        Command(
            type="object_update",
            id=obj.id,
            patch={"package_color_override": False, "package_friction_override": False},
        )
    )
    assert geom().rgba == pytest.approx([0.1, 0.2, 0.3, 1])
    assert session.sim.model.geom("obj_" + obj.id + "_1").friction == pytest.approx(
        [0.6, 0.004, 0.0002]
    )


def test_collection_randomization_explicitly_overrides_package_colors():
    from backend.collection_randomization import episode_scene
    from backend.collection_schema import Variation
    from backend.schema import Scene

    scene = Scene(objects=[read_package()])
    randomized = episode_scene(
        scene, Variation(object_colors=["#ff0000"], positions=False), 42
    )
    assert randomized.objects[0].package_color_override
    assert not scene.objects[0].package_color_override


def test_package_upload_api_preview_and_error_are_nonmutating():
    import base64
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/import/package",
            json={
                "files": [
                    {"path": p, "data": base64.b64encode(b).decode()}
                    for p, b in fixture_files().items()
                ]
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["mass"] == pytest.approx(0.045)
        sid = client.post("/api/sessions").json()["sessionId"]
        before = client.get("/api/sessions/" + sid).json()["scene"]
        bad = client.post(
            "/api/import/package", json={"files": [{"path": "../bad", "data": "eA=="}]}
        )
        assert bad.status_code == 422
        assert client.get("/api/sessions/" + sid).json()["scene"] == before
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as z:
            for p, b in fixture_files().items():
                z.writestr("folder/" + p, b)
        zipped = client.post(
            "/api/import/package",
            content=data.getvalue(),
            headers={"Content-Type": "application/zip"},
        )
        assert zipped.status_code == 200, zipped.text
        assert zipped.json()["package"] == response.json()["package"]


@pytest.mark.parametrize(
    "element,attribute",
    [
        ("body", 'gravcomp="1"'),
        ("geom", 'fluidshape="ellipsoid"'),
        ("freejoint", 'align="true"'),
    ],
)
def test_unsupported_physics_attributes_are_rejected(element, attribute):
    files = fixture_files()
    files["object.xml"] = files["object.xml"].replace(
        ("<" + element).encode(), ("<" + element + " " + attribute).encode(), 1
    )
    with pytest.raises(ValueError, match="Unsupported|unsupported"):
        read_package(files)


def test_static_child_mesh_transform_and_aggregate_inertia_survive_rebuild():
    import mujoco
    from backend.schema import Scene
    from backend.simulation import Simulation

    files = fixture_files()
    files["object.xml"] = b"""<mujocoinclude><body name="compound"><freejoint/>
      <geom type="box" size=".01 .01 .01" mass=".02"/>
      <body pos=".03 -.02 .01" quat=".7071067811865476 0 0 .7071067811865476">
        <geom type="mesh" mesh="case" pos=".01 .02 .03" rgba=".4 .5 .6 1" mass=".03"/>
      </body></body></mujocoinclude>"""
    obj = read_package(files)
    sim = Simulation(Scene(objects=[obj]))
    a = sim.model.geom("obj_" + obj.id + "_0").id
    b = sim.model.geom("obj_" + obj.id + "_1").id
    assert sim.data.geom_xpos[b] - sim.data.geom_xpos[a] == pytest.approx(
        [0.01, -0.01, 0.04], abs=1e-8
    )
    assert sim.model.body("object_" + obj.id).mass[0] == pytest.approx(0.05)
    # Mesh longest axis rotates from X to Y; prevents accidentally applying mesh frame twice.
    mid = sim.model.geom_dataid[b]
    start = sim.model.mesh_vertadr[mid]
    n = sim.model.mesh_vertnum[mid]
    points = (
        sim.model.mesh_vert[start : start + n] @ sim.data.geom_xmat[b].reshape(3, 3).T
    )
    assert np.ptp(points, axis=0) == pytest.approx([0.03, 0.05, 0.01], abs=1e-8)


def test_zip_rejects_symlink_duplicate_and_expansion_budget():
    from backend.package_importer import import_package_zip
    import stat

    for kind in ("symlink", "duplicate", "large"):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as z:
            if kind == "symlink":
                item = zipfile.ZipInfo("object.xml")
                item.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(item, "/tmp/outside")
            elif kind == "duplicate":
                z.writestr("object.xml", b"a")
                with pytest.warns(UserWarning):
                    z.writestr("object.xml", b"b")
            else:
                z.writestr("large.obj", b"0" * 20_000_001)
        with pytest.raises(ValueError):
            import_package_zip(raw.getvalue())


def test_inherited_frame_default_preserves_contact_and_color():
    files = {
        "scene.xml": b"""<mujoco><default><default class="sensor"><geom rgba="1 0 0 1" friction=".2 .02 .002"/></default></default><worldbody><frame childclass="sensor"><include file="object.xml"/></frame></worldbody></mujoco>""",
        "object.xml": b"""<mujocoinclude><body name="sphere"><freejoint/><geom type="sphere" size=".02" mass=".05"/></body></mujocoinclude>""",
    }
    obj = read_package(files)
    assert obj.package.geoms[0].rgba == pytest.approx([1, 0, 0, 1])
    assert obj.package.geoms[0].friction == pytest.approx([0.2, 0.02, 0.002])


def test_complete_object_xml_document_is_supported():
    obj = read_package(
        {
            "object.xml": b'<mujoco><worldbody><body name="sphere"><freejoint/><geom type="sphere" size=".02" mass=".05"/></body></worldbody></mujoco>'
        }
    )
    assert obj.name == "sphere"
    assert obj.mass == pytest.approx(0.05)
    assert obj.package.dimensions == pytest.approx([0.04, 0.04, 0.04])


def test_package_visual_meshes_are_in_the_browser_snapshot():
    from backend.schema import Scene
    from backend.simulation import Simulation

    obj = read_package()
    sim = Simulation(Scene(objects=[obj]))
    packet = sim.snapshot()
    visible = [
        g for g in packet["geometry"] if g["owner"] == obj.id and g["kind"] == "mesh"
    ]
    assert visible
    for geom in visible:
        assert str(geom["mesh"]) in packet["meshes"]
        assert len(packet["meshes"][str(geom["mesh"])]["vertices"]) > 0


@pytest.mark.parametrize("with_scene", [False, True])
def test_unnamed_rigid_root_with_unnamed_static_child(with_scene):
    body = b'<body><freejoint/><geom type="sphere" size=".02" mass=".05"/><body pos=".02 0 0"><geom type="sphere" size=".01" mass=".01"/></body></body>'
    files = {"object.xml": b"<mujocoinclude>" + body + b"</mujocoinclude>"}
    if with_scene:
        files["scene.xml"] = (
            b'<mujoco><worldbody><frame><include file="object.xml"/></frame></worldbody></mujoco>'
        )
    obj = read_package(files)
    assert obj.mass == pytest.approx(0.06)
    assert len(obj.package.geoms) == 2
