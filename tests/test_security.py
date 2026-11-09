from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import security


def test_ai_rate_limit_and_expiry(monkeypatch):
    security._hits.clear()
    clock = [100.0]
    monkeypatch.setattr(security, 'monotonic', lambda: clock[0])
    request = SimpleNamespace(client=SimpleNamespace(host='test-client'))
    for _ in range(30):
        security.limit_ai_requests(request)
    with pytest.raises(HTTPException) as error:
        security.limit_ai_requests(request)
    assert error.value.status_code == 429
    clock[0] += 61
    security.limit_ai_requests(request)
    security._hits.clear()


def test_validation_redacts_input_and_cors_is_restricted():
    client = TestClient(app)
    response = client.post('/api/investigations', json={'request': 'sensitive text', 'product_id': 'invalid'})
    assert response.status_code == 422 and 'sensitive text' not in response.text
    allowed = client.options('/api/chat', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
    denied = client.options('/api/chat', headers={'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'POST'})
    assert allowed.status_code == 200 and denied.status_code == 400


def test_unexpected_error_is_sanitized(monkeypatch, caplog):
    from backend.app.database import get_db
    def fail():
        raise RuntimeError('private database credentials')
    app.dependency_overrides[get_db] = fail
    try:
        response = TestClient(app).post('/api/chat', json={'question': 'battery'})
        assert response.status_code == 500
        assert 'private database credentials' not in response.text + caplog.text
    finally:
        app.dependency_overrides.clear()
