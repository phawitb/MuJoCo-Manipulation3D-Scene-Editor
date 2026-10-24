from fastapi.testclient import TestClient
from backend.main import app


def test_shared_http_and_websocket_session_and_revision_guard():
    with TestClient(app) as c:
        created = c.post("/api/sessions").json()
        sid = created["sessionId"]
        with c.websocket_connect("/ws?session=" + sid) as ws:
            assert ws.receive_json()["sessionId"] == sid
            result = c.post(
                f"/api/sessions/{sid}/command", json={"type": "example"}
            ).json()
            assert result["scene"]["task"]["source"] == "spoon"
            assert ws.receive_json()["scene"]["objects"][0]["id"] == "spoon"
            r = c.post(
                f"/api/sessions/{sid}/command",
                json={
                    "type": "task",
                    "source": "spoon",
                    "target": "cup",
                    "revision": 0,
                },
            )
            assert r.status_code == 409
            import time

            c.post(f"/api/sessions/{sid}/command", json={"type": "plan"})
            deadline = time.monotonic() + 30
            while (
                c.get(f"/api/sessions/{sid}").json()["plan"]["status"] == "calculating"
                and time.monotonic() < deadline
            ):
                time.sleep(0.02)
            r = c.post(f"/api/sessions/{sid}/command", json={"type": "run"})
            assert r.json()["running"] and r.json()["task"]["status"] == "running"
            r = c.post(f"/api/sessions/{sid}/command", json={"type": "pause"})
            assert not r.json()["running"]
            r = c.post(f"/api/sessions/{sid}/command", json={"type": "stop"})
            assert r.json()["task"]["status"] == "cancelled"
        assert c.delete(f"/api/sessions/{sid}").status_code == 200
        assert c.get(f"/api/sessions/{sid}").status_code == 404


def test_run_requires_instruction_and_camera_updates_are_authoritative():
    with TestClient(app) as c:
        sid = c.post("/api/sessions").json()["sessionId"]
        url = f"/api/sessions/{sid}/command"
        assert c.post(url, json={"type": "run"}).status_code == 422
        result = c.post(
            url,
            json={
                "type": "camera",
                "camera": "front",
                "value": {"position": [1, -1, 1.3], "target": [0, 0, 0.8]},
            },
        )
        assert result.json()["scene"]["cameras"]["front"]["position"] == [1, -1, 1.3]
        assert c.post(url, json={"type": "step", "count": 1000000}).status_code == 422
        assert (
            c.post(
                url, json={"type": "task", "source": "missing", "target": "cup"}
            ).status_code
            == 422
        )


def test_local_api_rejects_foreign_origin_and_unknown_session():
    with TestClient(app) as c:
        assert (
            c.post(
                "/api/sessions", headers={"origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert c.get("/api/sessions/no-such-session").status_code == 404


def test_idle_browser_sessions_are_reclaimed_at_capacity():
    from backend.sessions import Registry
    import asyncio

    async def exercise():
        registry = Registry()
        try:
            first = await registry.create(ephemeral=True)
            for _ in range(16):
                await registry.create(ephemeral=True)
            assert len(registry.items) == 16
            assert first.id not in registry.items
        finally:
            await registry.close()

    asyncio.run(exercise())


def test_backpressure_preserves_structure_and_latest_physics_state():
    import asyncio
    from backend.sessions import Command, Session

    s = Session()
    queue = asyncio.Queue(maxsize=3)
    s.subscribers.add(queue)
    s.broadcast(s.execute(Command(type="example")))
    s.broadcast(s.execute(Command(type="physics")))
    for _ in range(5):
        s.broadcast(s.tick(1))
    packets = []
    while not queue.empty():
        packets.append(queue.get_nowait())
    snapshots = [p for p in packets if p["type"] == "snapshot"]
    assert snapshots and snapshots[-1]["scene"]["task"]["source"] == "spoon"
    assert packets[-1]["sequence"] == s.sequence
    assert packets[-1]["revision"] == snapshots[-1]["revision"]
