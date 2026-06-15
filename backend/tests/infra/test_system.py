from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_returns_service_info():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "eira-backend"
    assert "version" in body
