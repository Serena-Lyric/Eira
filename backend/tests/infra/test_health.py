import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz_alive(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_checks_dependencies(client):
    resp = client.get("/readyz")
    assert resp.status_code in (200, 503)
    body = resp.json()
    for k in ("db", "redis", "oss"):
        assert k in body


def test_metrics_endpoint_exists(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "python_gc_objects_collected_total" in resp.text
