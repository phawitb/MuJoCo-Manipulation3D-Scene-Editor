import base64
import importlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_blender import picture


def client():
    try:
        routes = importlib.import_module('backend.modules.blender.routes')
    except ModuleNotFoundError:
        pytest.fail('Blender routes have not been implemented')
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_create_route_returns_glb_and_portable_mesh():
    response = client().post('/api/blender/create', json={'image_base64': base64.b64encode(picture()).decode()})
    assert response.status_code == 200, response.text
    result = response.json()
    assert base64.b64decode(result['glb_base64'])[:4] == b'glTF'
    assert result['object']['mesh']['faces']
    assert result['metadata']['watertight']


def test_route_validation_reports_client_errors_and_limits_streamed_body():
    app = client()
    for data in [{'image_base64': 'bad!'}, {'image_base64': 'AAAA', 'extra': True}, {'image_base64': 'AAAA', 'width_m': -1}]:
        response = app.post('/api/blender/create', json=data)
        assert response.status_code == 422
        assert response.json()['detail']
    assert app.post('/api/blender/create', content=b' ' * 8_100_001).status_code == 413
