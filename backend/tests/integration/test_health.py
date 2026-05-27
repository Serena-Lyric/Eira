from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthz_alive():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_checks_dependencies():
    resp = client.get("/readyz")
    assert resp.status_code in (200, 503)
    body = resp.json()
    for k in ("db", "redis", "oss"):
        assert k in body


def test_metrics_endpoint_exists():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "process_cpu_seconds_total" in resp.text
