from fastapi.testclient import TestClient
from backend.main import app


def receive(ws, kind):
    for _ in range(50):
        data = ws.receive_json()
        if data['type'] == kind:
            return data
    raise AssertionError(f'No {kind} packet')


def test_http_metadata_and_websocket_controls():
    with TestClient(app) as client:
        assert client.get('/api/health').json()['engine'] == 'MuJoCo'
        assert len(client.get('/api/assets').json()) == 4
        assert len(client.get('/api/meshes').json()) >= 10
        with client.websocket_connect('/ws') as ws:
            initial = receive(ws, 'snapshot')
            assert initial['scene']['objects'] == [] and not initial['running']
            ws.send_json({'type':'step', 'requestId':'s'})
            stepped = receive(ws, 'state')
            assert stepped['time'] > 0
            ws.send_json({'type':'run'})
            assert receive(ws, 'state')['running']
            ws.send_json({'type':'pause'})
            paused = receive(ws, 'snapshot')
            assert not paused['running']
            ws.send_json({'type':'load', 'scene':{'objects':[{'id':'bad', 'mass':-1}]}})
            assert receive(ws, 'error')['message']
            ws.send_json({'type':'reset'})
            assert receive(ws, 'snapshot')['time'] == 0
            ws.send_json({'type':'unknown'})
            assert receive(ws, 'error')['message']


def test_edit_rejected_during_run_and_revision_conflict():
    with TestClient(app) as client, client.websocket_connect('/ws') as ws:
        snap = receive(ws, 'snapshot')
        ws.send_json({'type':'load', 'scene':snap['scene'], 'revision':999})
        assert 'stale' in receive(ws, 'error')['message'].lower()
        ws.send_json({'type':'run'})
        receive(ws, 'state')
        ws.send_json({'type':'load', 'scene':snap['scene']})
        assert 'pause' in receive(ws, 'error')['message'].lower()
