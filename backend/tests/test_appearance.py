import numpy as np
import pytest
from pydantic import ValidationError
from backend.schema import Scene
from backend.sessions import Session, Command
from backend.planning import physics_fingerprint


def test_legacy_defaults_and_invalid_appearance():
    scene = Scene.model_validate({})
    assert scene.appearance.table.pattern == "solid"
    for value in [
        {"key_intensity": -1},
        {"robot": {"pattern": "invalid"}},
        {"background": "red"},
    ]:
        with pytest.raises(ValidationError):
            Scene.model_validate({"appearance": value})


def test_seeded_randomization_scopes_and_physics_preserved():
    session = Session()
    session.execute(Command(type="example"))
    session.sim.step(20)
    before = session.sim.export_scene().model_dump()
    qpos, qvel, ctrl = [
        x.copy()
        for x in (session.sim.data.qpos, session.sim.data.qvel, session.sim.data.ctrl)
    ]
    time = session.sim.data.time
    fingerprint = physics_fingerprint(session.sim)
    cmd = Command(
        type="randomize_appearance",
        value={"seed": 42, "groups": ["table"], "strength": "wide"},
    )
    first = session.execute(cmd)["scene"]
    assert first["appearance"]["table"] != before["appearance"]["table"]
    assert first["appearance"]["robot"] == before["appearance"]["robot"]
    assert first["robot"] == before["robot"]
    assert first["objects"] == before["objects"]
    assert first["cameras"] == before["cameras"]
    assert first["table"]["width"] == before["table"]["width"]
    assert physics_fingerprint(session.sim) == fingerprint
    for actual, expected in zip(
        (session.sim.data.qpos, session.sim.data.qvel, session.sim.data.ctrl),
        (qpos, qvel, ctrl),
    ):
        np.testing.assert_array_equal(actual, expected)
    assert session.sim.data.time == time
    assert session.execute(cmd)["scene"] == first
    assert (
        session.execute(
            Command(
                type="randomize_appearance", value={"seed": 43, "groups": ["table"]}
            )
        )["scene"]
        != first
    )


def test_appearance_roundtrip_and_example_retention():
    session = Session()
    appearance = session.sim.scene.model_dump().get("appearance", {})
    appearance.update(
        background="#334455", environment="warehouse", robot_color="#ff0066"
    )
    result = session.execute(Command(type="appearance", value=appearance))
    assert result["scene"]["appearance"]["environment"] == "warehouse"
    restored = Scene.model_validate(result["scene"])
    assert restored.appearance.background == "#334455"
    for kind in ("example", "reset"):
        packet = session.execute(Command(type=kind))
        assert packet["scene"]["appearance"] == result["scene"]["appearance"]
    model = session.sim.model
    for i in range(model.ngeom):
        if (model.geom(i).name or "").startswith("decor_"):
            assert model.geom_contype[i] == model.geom_conaffinity[i] == 0


def test_invalid_randomization_is_atomic_and_running_edits_rejected():
    s = Session()
    before = s.packet()["scene"]
    for value in ({"seed": -1}, {"groups": ["typo"]}, {"strength": "extreme"}):
        with pytest.raises(ValueError):
            s.execute(Command(type="randomize_appearance", value=value))
        assert s.packet()["scene"] == before
    s.sim.running = True
    with pytest.raises(ValueError, match="Pause"):
        s.execute(Command(type="randomize_appearance", value={"seed": 4}))


def test_native_patterns_and_recipes_api():
    import io
    from PIL import Image
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as c:
        sid = c.post("/api/sessions").json()["sessionId"]
        url = f"/api/sessions/{sid}"
        before = np.array(
            Image.open(io.BytesIO(c.get(url + "/image?view=top").content))
        )
        config = c.get("/api/appearance/presets").json()[4]
        result = c.post(
            url + "/command",
            json={
                "type": "appearance",
                "value": config["appearance"],
                "patch": {"tableColor": config["tableColor"]},
            },
        )
        assert result.status_code == 200
        assert any(m["texture"] for m in result.json()["materials"].values())
        after = np.array(Image.open(io.BytesIO(c.get(url + "/image?view=top").content)))
        assert np.abs(before.astype(float) - after).mean() > 10
        body = dict(
            scene=result.json()["scene"],
            seed=10,
            count=3,
            groups=["table"],
            strength="wide",
        )
        response = c.post("/api/appearance/variants", json=body)
        assert response.status_code == 200
        recipes = response.json()["scenes"]
        assert len(recipes) == 3
        assert (
            recipes[0]
            == c.post("/api/appearance/variants", json=body).json()["scenes"][0]
        )
        assert recipes[0]["appearance"] != recipes[1]["appearance"]
        assert (
            c.post(
                "/api/appearance/variants", json={**body, "count": 10000}
            ).status_code
            == 422
        )


def test_native_effective_surface_colors_and_untinted_texture():
    import mujoco
    from backend.simulation import Simulation

    scene = Scene.model_validate(
        {
            "appearance": {
                "floor_color": "#ff0000",
                "leg_color": "#00ff00",
                "table": {"pattern": "checker", "secondary": "#ffffff"},
            }
        }
    )
    sim = Simulation(scene)
    view = mujoco.MjvScene(sim.model, maxgeom=1000)
    mujoco.mjv_updateScene(
        sim.model,
        sim.data,
        mujoco.MjvOption(),
        None,
        mujoco.MjvCamera(),
        mujoco.mjtCatBit.mjCAT_ALL,
        view,
    )
    for name, color in [
        ("floor", [1, 0, 0, 1]),
        ("leg_1_1", [0, 1, 0, 1]),
        ("table", [1, 1, 1, 1]),
    ]:
        geom = next(
            g
            for g in view.geoms[: view.ngeom]
            if g.objid == sim.model.geom(name).id
            and g.objtype == mujoco.mjtObj.mjOBJ_GEOM
        )
        np.testing.assert_allclose(geom.rgba, color)


def test_all_scopes_preserve_physical_parameters_and_prepared_plan():
    session = Session()
    session.execute(Command(type="example"))
    session.sim.step(10)
    model = session.sim.model
    physical = {
        name: getattr(model, name).copy()
        for name in [
            "body_mass",
            "body_inertia",
            "jnt_range",
            "actuator_gainprm",
            "actuator_biasprm",
        ]
    }
    mask = (model.geom_contype != 0) | (model.geom_conaffinity != 0)
    physical_geoms = {
        name: getattr(model, name)[mask].copy()
        for name in [
            "geom_contype",
            "geom_conaffinity",
            "geom_friction",
            "geom_size",
            "geom_pos",
        ]
    }
    fingerprint = physics_fingerprint(session.sim)
    session.plan = {
        "status": "ready",
        "verified": True,
        "fingerprint": fingerprint,
        "points": [],
    }
    policy = session.sim.policy
    session.execute(
        Command(type="randomize_appearance", value={"seed": 91, "strength": "wide"})
    )
    assert physics_fingerprint(session.sim) == fingerprint
    assert session.plan["status"] == "ready"
    assert session.sim.policy is policy
    for name, values in physical.items():
        np.testing.assert_array_equal(getattr(session.sim.model, name), values)
    updated = session.sim.model
    mask = (updated.geom_contype != 0) | (updated.geom_conaffinity != 0)
    for name, values in physical_geoms.items():
        np.testing.assert_array_equal(getattr(updated, name)[mask], values)
